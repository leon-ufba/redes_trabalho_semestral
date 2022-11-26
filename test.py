import re
import datetime

hostsBySegs = {
  "recepcao": {
    "aa:aa:aa:aa:aa:aa",
    "bb:bb:bb:bb:bb:bb"
  },
  "financeiro": {
    "cc:cc:cc:cc:cc:cc",
  }
}

allowRules = [
  {
    "host_a": "cc:cc:cc:cc:cc:cc",
    "host_b": "bb:bb:bb:bb:bb:bb",
    "acao": "permitir",
  },
]

denyRules = [
  {
    "segmento_a": "recepcao",
    "segmento_b": "financeiro",
    "acao": "bloquear"
  },
  {
    "host": "bb:bb:bb:bb:bb:bb",
    "segmento": "financeiro",
    "acao": "bloquear"
  },
]

def whichSegment(mac):
  for seg in hostsBySegs:
    if mac in hostsBySegs[seg]:
      return seg
  return None

def mapDay(day):
  dayDict = { 'seg': 0, 'ter': 1, 'qua': 2, 'qui': 3, 'sex': 4, 'sab': 5, 'dom': 6 }
  return dayDict[day] if(day in dayDict) else None

def parseTime(tstr):
  if(tstr == None):
    return None
  try:
    n = tstr.lower().replace('á', 'a')
    l = re.split(r' |-|:', n)
    if(len(l) != 6):
      return None
    l[0] = mapDay(l[0])
    l[1] = mapDay(l[1])
    if(l[0] == None or l[1] == None):
      return None
    l[2:] = map(int, l[2:])
    if((l[2] < 0 or l[2] > 23) or (l[3] < 0 or l[3] > 59) or (l[4] < 0 or l[4] > 23) or (l[5] < 0 or l[5] > 59)):
      return None
    return tuple(l)
  except:
    return None

def isOnTime(r):
  l = parseTime(r.get('horario'))
  if(l == None):
    return True
  else:
    startWeekDay, endWeekDay, startHour, startMinute, endHour, endMinute = l
    now = datetime.datetime.today()
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

def checkRules(rules, src, dst, src_seg, dst_seg):
  priority = 4
  reverseWay = True
  check = False
  if(src_seg == None or dst_seg == None):
    return check, priority
  else:
    for r in rules:
      if(priority > 1 and r.get('host_a') == src and r.get('host_b') == dst):
        if(isOnTime(r)):
          check = True
          priority = 1
      if(priority > 1 and r.get('host_a') == dst and r.get('host_b') == src and reverseWay):
        if(isOnTime(r)):
          check = True
          priority = 1
      if(priority > 2 and r.get('host') == src and r.get('segmento') == dst_seg):
        if(isOnTime(r)):
          check = True
          priority = 2
      if(priority > 2 and r.get('host') == dst and r.get('segmento') == src_seg and reverseWay):
        if(isOnTime(r)):
          check = True
          priority = 2
      if(priority > 3 and r.get('segmento_a') == src_seg and r.get('segmento_b') == dst_seg):
        if(isOnTime(r)):
          check = True
          priority = 3
      if(priority > 3 and r.get('segmento_a') == dst_seg and r.get('segmento_b') == src_seg and reverseWay):
        if(isOnTime(r)):
          check = True
          priority = 3
    return check, priority

def isDenied(src, dst, src_seg, dst_seg):
  return checkRules(denyRules, src, dst, src_seg, dst_seg)

def isAllowed(src, dst, src_seg, dst_seg):
  return checkRules(allowRules, src, dst, src_seg, dst_seg)

def canPass(src, dst, src_seg, dst_seg):
  denied, deniedPriority = isDenied(src, dst, src_seg, dst_seg)
  allowed, allowedPriority = isAllowed(src, dst, src_seg, dst_seg)

  print(allowed, allowedPriority, denied, deniedPriority)
  if(deniedPriority > allowedPriority):
    return allowed
  elif(deniedPriority < allowedPriority):
    return not denied
  else:
    return not denied


src = 'bb:bb:bb:bb:bb:bb'
dst = 'cc:cc:cc:cc:cc:cc'

src_seg = whichSegment(src)
dst_seg = whichSegment(dst)

print(src, dst, src_seg, dst_seg)

d = canPass(src, dst, src_seg, dst_seg)

print('canPass:', d)

