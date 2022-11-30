import json
import re
from datetime import datetime

from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet, ipv4
from ryu.app.wsgi import ControllerBase
from ryu.app.wsgi import Response
from ryu.app.wsgi import route
from ryu.app.wsgi import WSGIApplication
from ryu.lib import dpid as dpid_lib

myapp_name = 'simpleswitch'
counter = 0

portByMacBySwitch = {
  2: {
    '00:00:00:00:00:f4': 2,
  },
  3: {
    '00:00:00:00:00:f1': 1,
    '00:00:00:00:00:f2': 2,
    '00:00:00:00:00:f3': 3,
  },
  5: {
    '00:00:00:00:00:f5': 1,
    '00:00:00:00:00:f6': 2,
    '00:00:00:00:00:f7': 3,
  },
  6: {
    '00:00:00:00:00:f8': 1,
    '00:00:00:00:00:f9': 2,
  },
}

class SimpleSwitch(app_manager.RyuApp):
  _CONTEXTS = {'wsgi': WSGIApplication}
  OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

  def __init__(self, *args, **kwargs):
    super(SimpleSwitch, self).__init__(*args, **kwargs)
    wsgi = kwargs['wsgi']
    wsgi.register(SimpleSwitchController,
                  {myapp_name: self})

    # learn mac addresses on each port of each switch
    self.mac_to_port = {}
    self.hostsBySegs = {}
    self.bandwidthRules = []
    self.allowRules = []
    self.denyRules = []

  def whichSegment(self, mac):
    hostsBySegs = self.hostsBySegs
    for seg in hostsBySegs:
      if mac in hostsBySegs[seg]:
        return seg
    return None

  def mapDay(self, day):
    dayDict = { 'seg': 0, 'ter': 1, 'qua': 2, 'qui': 3, 'sex': 4, 'sab': 5, 'dom': 6 }
    return dayDict[day] if(day in dayDict) else None

  def parseTime(self, tstr):
    if(tstr == None):
      return None
    try:
      n = tstr.lower().replace('á', 'a')
      l = re.split(r' |-|:', n)
      if(len(l) != 6):
        return None
      l[0] = self.mapDay(l[0])
      l[1] = self.mapDay(l[1])
      if(l[0] == None or l[1] == None):
        return None
      l[2:] = map(int, l[2:])
      if((l[2] < 0 or l[2] > 23) or (l[3] < 0 or l[3] > 59) or (l[4] < 0 or l[4] > 23) or (l[5] < 0 or l[5] > 59)):
        return None
      return tuple(l)
    except:
      return None
  
  def isOnTime(self, r):
    l = self.parseTime(r.get('horario'))
    if(l == None):
      return True
    else:
      startWeekDay, endWeekDay, startHour, startMinute, endHour, endMinute = l
      now = datetime.today()
      nowWeekDay = now.weekday()
      nowHour = now.hour
      nowMinute = now.minute
      if(startWeekDay <= endWeekDay):
        if(nowWeekDay < startWeekDay or nowWeekDay > endWeekDay):
          return False
      else:
        if(nowWeekDay < startWeekDay and nowWeekDay > endWeekDay):
          return False

      if(nowHour < startHour or nowHour > endHour):
        return False
      elif(nowHour == startHour and nowMinute < startMinute):
        return False
      elif(nowHour == endHour and nowMinute > endMinute):
        return False
      
      return True

  def checkRules(self, rules, src, dst, src_seg, dst_seg):
    priority = 4
    reverseWay = True
    check = False
    if(src_seg == None or dst_seg == None):
      return check, priority
    else:
      for r in rules:
        if(priority > 1 and r.get('host_a') == src and r.get('host_b') == dst):
          if(self.isOnTime(r)):
            check = True
            priority = 1
        if(priority > 1 and r.get('host_a') == dst and r.get('host_b') == src and reverseWay):
          if(self.isOnTime(r)):
            check = True
            priority = 1
        if(priority > 2 and r.get('host') == src and r.get('segmento') == dst_seg):
          if(self.isOnTime(r)):
            check = True
            priority = 2
        if(priority > 2 and r.get('host') == dst and r.get('segmento') == src_seg and reverseWay):
          if(self.isOnTime(r)):
            check = True
            priority = 2
        if(priority > 3 and r.get('segmento_a') == src_seg and r.get('segmento_b') == dst_seg):
          if(self.isOnTime(r)):
            check = True
            priority = 3
        if(priority > 3 and r.get('segmento_a') == dst_seg and r.get('segmento_b') == src_seg and reverseWay):
          if(self.isOnTime(r)):
            check = True
            priority = 3
      return check, priority

  def isDenied(self, src, dst, src_seg, dst_seg):
    return self.checkRules(self.denyRules, src, dst, src_seg, dst_seg)

  def isAllowed(self, src, dst, src_seg, dst_seg):
    return self.checkRules(self.allowRules, src, dst, src_seg, dst_seg)

  def canPass(self, src, dst, src_seg, dst_seg):
    if(src_seg == None or dst_seg == None):
      return False
    denied, deniedPriority = self.isDenied(src, dst, src_seg, dst_seg)
    allowed, allowedPriority = self.isAllowed(src, dst, src_seg, dst_seg)
    if(deniedPriority > allowedPriority):
      return allowed
    elif(deniedPriority < allowedPriority):
      return not denied
    else:
      return not denied
  
  def bandLimit(self, src, dst, src_seg, dst_seg):
    limit = 3
    priority = 4
    reverseWay = True
    limitDict = { '1Mbps': 0, '10Mbps': 1, '20Mbps': 2 }
    if(src_seg == None or dst_seg == None):
      return None
    else:
      for r in self.bandwidthRules:
        l = limitDict.get(r.get('banda_download'))
        l = 3 if (l == None) else l
        if(l > limit):
          continue
        if(priority >= 1 and r.get('host_a') == src and r.get('host_b') == dst):
          if(self.isOnTime(r)):
            limit = l
            priority = 1
        if(priority >= 1 and r.get('host_a') == dst and r.get('host_b') == src and reverseWay):
          if(self.isOnTime(r)):
            limit = l
            priority = 1
        if(priority >= 2 and r.get('host') == src and r.get('segmento') == dst_seg):
          if(self.isOnTime(r)):
            limit = l
            priority = 2
        if(priority >= 2 and r.get('host') == dst and r.get('segmento') == src_seg and reverseWay):
          if(self.isOnTime(r)):
            limit = l
            priority = 2
        if(priority >= 3 and r.get('segmento_a') == src_seg and r.get('segmento_b') == dst_seg):
          if(self.isOnTime(r)):
            limit = l
            priority = 3
        if(priority >= 3 and r.get('segmento_a') == dst_seg and r.get('segmento_b') == src_seg and reverseWay):
          if(self.isOnTime(r)):
            limit = l
            priority = 3
      limit = limit if (limit < 3) else None
      return limit

  def add_flow(self, hto, datapath, match, actions, priority=1000, buffer_id=None):
    ofproto = datapath.ofproto
    parser = datapath.ofproto_parser

    hard_timeout = 3 if hto else 0
    
    inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)] if actions else []
    if buffer_id:
      mod = parser.OFPFlowMod(
        datapath=datapath,
        buffer_id=buffer_id,
        priority=priority,
        match=match,
        instructions=inst,
        hard_timeout=hard_timeout
      )
    else:
      mod = parser.OFPFlowMod(
        datapath=datapath,
        priority=priority,
        match=match,
        instructions=inst,
        hard_timeout=hard_timeout
      )
    datapath.send_msg(mod)

  def delete_flow(self, datapath):
    ofproto = datapath.ofproto
    parser = datapath.ofproto_parser
    match = parser.OFPMatch()
    mod = parser.OFPFlowMod(
      datapath,
      command=ofproto.OFPFC_DELETE,
      match=match,
      out_port=ofproto.OFPP_ANY,
      out_group=ofproto.OFPG_ANY
    )
    datapath.send_msg(mod)

  @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
  def switch_features_handler(self, ev):
    msg = ev.msg
    dp = ev.msg.datapath
    ofp = dp.ofproto
    parser = dp.ofproto_parser
    self.delete_flow(dp)
    match = parser.OFPMatch()
    actions = [parser.OFPActionOutput(ofp.OFPP_CONTROLLER, ofp.OFPCML_NO_BUFFER)]
    self.add_flow(False, dp, match, actions, priority=0)

  @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
  def packet_in_handler(self, ev):
    global portByMacBySwitch, counter

    msg = ev.msg
    dp = msg.datapath
    ofp = dp.ofproto
    ofp_parser = dp.ofproto_parser
    in_port = msg.match['in_port']

    pkt = packet.Packet(msg.data)
    eth = pkt.get_protocols(ethernet.ethernet)[0]

    src = eth.src
    dst = eth.dst

    src_seg = self.whichSegment(src)
    dst_seg = self.whichSegment(dst)

    canPass = self.canPass(src, dst, src_seg, dst_seg)

    dpid = dp.id
    self.mac_to_port.setdefault(dpid, {})

    # learn a mac address to avoid FLOOD next time.
    self.mac_to_port[dpid][src] = in_port

    if dst in self.mac_to_port[dpid]:
      out_port = self.mac_to_port[dpid][dst]
    else:
      out_port = ofp.OFPP_FLOOD

    actions = [ofp_parser.OFPActionOutput(out_port)]

    # install a flow to avoid packet_in next time
    if out_port != ofp.OFPP_FLOOD:

      queue_id = None
      limit = self.bandLimit(src, dst, src_seg, dst_seg)
      portOfSwitch = portByMacBySwitch.get(dp.id)
      p = portOfSwitch.get(src) if portOfSwitch else None
      if(dpid != None and p != None and limit != None):
        queue_id = str(dpid) + str(p) + str(limit)
        queue_id = int(queue_id)
      if(queue_id != None):
        actions.insert(0, ofp_parser.OFPActionSetQueue(queue_id=queue_id))
      
      # counter = counter + 1
      # if('00:00:00:00:00:f1' in [src, dst] and '00:00:00:00:00:f9' in [src, dst]):
      #   print([str(datetime.now()), [src, dst, canPass, queue_id], counter])

      match = ofp_parser.OFPMatch(in_port=in_port, eth_dst=dst)

      if(not canPass):
        self.add_flow(True, dp, match, [])
        return

      if msg.buffer_id != ofp.OFP_NO_BUFFER:
        self.add_flow(True, dp, match, actions, buffer_id=msg.buffer_id)
        return
      else:
        self.add_flow(True, dp, match, actions)

    data = None
    if msg.buffer_id == ofp.OFP_NO_BUFFER:
      data = msg.data

    out = ofp_parser.OFPPacketOut(
      datapath=dp, buffer_id=msg.buffer_id, in_port=in_port,
      actions=actions, data = data)
    dp.send_msg(out)

class SimpleSwitchController(ControllerBase):

  def __init__(self, req, link, data, **config):
      super(SimpleSwitchController, self).__init__(req, link, data, **config)
      self.simple_switch_app = data[myapp_name]

  # debug
  @route('', '/debug/', methods=['POST'])
  def dbg(self, req, **kwargs):
    try:
      d = req.json_body

      src = d.get('src')
      dst = d.get('dst')

      src_seg = self.simple_switch_app.whichSegment(src)
      dst_seg = self.simple_switch_app.whichSegment(dst)

      canPass = self.simple_switch_app.canPass(src, dst, src_seg, dst_seg)

      body = json.dumps({
        'src': src,
        'src_seg': src_seg,
        'dst': dst,
        'dst_seg': dst_seg,
        'canPass': canPass,
      })
      
      return Response(content_type='application/json', body=str(body))
    except Exception as e:
      return Response(status=500, body=str(e))

  # questão 1
  @route('', '/nac/segmentos/', methods=['POST'])
  def r1(self, req, **kwargs):
    try:
      d = req.json_body
      hostsBySegs = self.simple_switch_app.hostsBySegs
      for seg in d:
        if(seg in hostsBySegs):
          hostsBySegs[seg].extend(x for x in d[seg] if x not in hostsBySegs[seg])
        else:
          hostsBySegs[seg] = d[seg]
      body = json.dumps(hostsBySegs)
      return Response(content_type='application/json', body=body)
    except:
      return Response(status=500)

  # questão 2
  @route('', '/nac/segmentos/', methods=['GET'])
  def r2(self, req, **kwargs):
    try:
      hostsBySegs = self.simple_switch_app.hostsBySegs
      body = json.dumps(hostsBySegs)
      return Response(content_type='application/json', body=body)
    except:
      return Response(status=500)

  # questão 3a
  @route('', '/nac/segmentos/{segment}', methods=['DELETE'])
  def r3a(self, req, **kwargs):
    try:
      hostsBySegs = self.simple_switch_app.hostsBySegs
      seg = kwargs['segment']
      if(seg in hostsBySegs):
        hostsBySegs.pop(seg)
      body = json.dumps(hostsBySegs)
      return Response(content_type='application/json', body=body)
    except:
      return Response(status=500)

  # questão 3b
  @route('', '/nac/segmentos/{segment}/{host}', methods=['DELETE'])
  def r3b(self, req, **kwargs):
    try:
      hostsBySegs = self.simple_switch_app.hostsBySegs
      seg = kwargs['segment']
      hst = kwargs['host']
      if(seg in hostsBySegs):
        if(hst in hostsBySegs[seg]):
          hostsBySegs[seg].remove(hst)
      body = json.dumps(hostsBySegs)
      return Response(content_type='application/json', body=body)
    except:
      return Response(status=500)

  # questões 4 a 8
  @route('', '/nac/controle/', methods=['POST'])
  def r4_8(self, req, **kwargs):
    try:
      d = req.json_body
      allowRules = self.simple_switch_app.allowRules
      denyRules  = self.simple_switch_app.denyRules
      bandwidthRules  = self.simple_switch_app.bandwidthRules
      if(d.get('banda_download')):
        if(d not in bandwidthRules):
          bandwidthRules.append(d)
      else:
        if(d.get('acao') == 'permitir'):
          if(d not in allowRules):
            allowRules.append(d)
        elif(d.get('acao') == 'bloquear'):
          if(d not in denyRules):
            denyRules.append(d)
      body = json.dumps([*allowRules, *denyRules, *bandwidthRules])
      return Response(content_type='application/json', body=body)
    except:
      return Response(status=500)

  # questão 9
  @route('', '/nac/controle/', methods=['GET'])
  def r9(self, req, **kwargs):
    try:
      allowRules = self.simple_switch_app.allowRules
      denyRules  = self.simple_switch_app.denyRules
      bandwidthRules  = self.simple_switch_app.bandwidthRules
      body = json.dumps([*allowRules, *denyRules, *bandwidthRules])
      return Response(content_type='application/json', body=body)
    except:
      return Response(status=500)

  # questão 10
  @route('', '/nac/controle/', methods=['DELETE'])
  def r10(self, req, **kwargs):
    try:
      d = req.json_body
      allowRules = self.simple_switch_app.allowRules
      denyRules  = self.simple_switch_app.denyRules
      bandwidthRules  = self.simple_switch_app.bandwidthRules
      if(d.get('banda_download')):
        if(d in bandwidthRules):
          bandwidthRules.remove(d)
      else:
        if(d.get('acao') == 'permitir'):
          if(d in allowRules):
            allowRules.remove(d)
        elif(d.get('acao') == 'bloquear'):
          if(d in denyRules):
            denyRules.remove(d)
      body = json.dumps([*allowRules, *denyRules, *bandwidthRules])
      return Response(content_type='application/json', body=body)
    except:
      return Response(status=500)
