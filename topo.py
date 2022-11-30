#!/usr/bin/env python

from mininet.net import Mininet
from mininet.node import Controller, RemoteController, OVSController
from mininet.node import CPULimitedHost, Host, Node
from mininet.node import OVSKernelSwitch, UserSwitch
from mininet.node import IVSSwitch
from mininet.cli import CLI
from mininet.log import setLogLevel, info
from mininet.link import TCLink, Intf
from subprocess import call, run

def myNetwork():

  net = Mininet( topo=None,
                 build=False,
                 ipBase='10.0.0.0/8')

  info( '*** Adding controller\n' )
  info( '*** Add switches\n')
  distribuicaoA = net.addSwitch('s1', cls=OVSKernelSwitch, dpid='0000000000000001')
  acessoA2      = net.addSwitch('s2', cls=OVSKernelSwitch, dpid='0000000000000002')
  acessoA1      = net.addSwitch('s3', cls=OVSKernelSwitch, dpid='0000000000000003')
  distribuicaoB = net.addSwitch('s4', cls=OVSKernelSwitch, dpid='0000000000000004')
  acessoB1      = net.addSwitch('s5', cls=OVSKernelSwitch, dpid='0000000000000005')
  acessoB2      = net.addSwitch('s6', cls=OVSKernelSwitch, dpid='0000000000000006')

  info( '*** Add hosts\n')
  visitante1 = net.addHost('visitante1', cls=Host, ip='10.100.254.1/8', defaultRoute=None, mac='00:00:00:00:00:f1')
  visitante2 = net.addHost('visitante2', cls=Host, ip='10.100.254.2/8', defaultRoute=None, mac='00:00:00:00:00:f2')
  recepcao   = net.addHost('recepcao',   cls=Host, ip='10.100.90.1/8',  defaultRoute=None, mac='00:00:00:00:00:f3')
  vendas     = net.addHost('vendas',     cls=Host, ip='10.100.80.1/8',  defaultRoute=None, mac='00:00:00:00:00:f4')
  rh         = net.addHost('rh',         cls=Host, ip='10.100.70.1/8',  defaultRoute=None, mac='00:00:00:00:00:f5')
  diretoria  = net.addHost('diretoria',  cls=Host, ip='10.100.60.1/8',  defaultRoute=None, mac='00:00:00:00:00:f6')
  financeiro = net.addHost('financeiro', cls=Host, ip='10.100.50.1/8',  defaultRoute=None, mac='00:00:00:00:00:f7')
  ti         = net.addHost('ti',         cls=Host, ip='10.100.2.1/8',   defaultRoute=None, mac='00:00:00:00:00:f8')
  internet   = net.addHost('internet',   cls=Host, ip='10.100.1.1/8',   defaultRoute=None, mac='00:00:00:00:00:f9')

  info( '*** Add links\n')
  net.addLink(visitante1, acessoA1, 0, 1)
  net.addLink(visitante2, acessoA1, 0, 2)
  net.addLink(recepcao,   acessoA1, 0, 3)
  net.addLink(acessoA1,   acessoA2, 4, 1)
  net.addLink(vendas,     acessoA2, 0, 2)
  net.addLink(acessoA2,   distribuicaoA, 3, 1)

  net.addLink(rh,         acessoB1, 0, 1)
  net.addLink(diretoria,  acessoB1, 0, 2)
  net.addLink(financeiro, acessoB1, 0, 3)
  net.addLink(acessoB1,   distribuicaoB, 4, 1)

  net.addLink(ti,         acessoB2, 0, 1)
  net.addLink(internet,   acessoB2, 0, 2)
  net.addLink(acessoB2,   distribuicaoB, 3, 2)

  net.addLink(distribuicaoA, distribuicaoB, 2, 3)

  info( '*** Starting network\n')
  net.build()
  info( '*** Starting controllers\n')
  for controller in net.controllers:
    controller.start()

  info( '*** Starting switches\n')
  net.get('s1').start([])
  net.get('s2').start([])
  net.get('s3').start([])
  net.get('s4').start([])
  net.get('s5').start([])
  net.get('s6').start([])

  info( '*** Post configure switches and hosts\n')

  try:
    for s in net.switches:
      run(['sudo', 'ovs-vsctl', 'set-controller', str(s), 'tcp:127.0.0.1:6653'])
    
    rates = [int(x) for x in [1e6, 10e6, 20e6]]
    # for s in net.switches:
    #   intfs = list(net.get(str(s)).intfs.values())
    #   for i in range(1, len(intfs)):
    #     for r in range(len(rates)):
    #       intf = str(intfs[i])
    #       queueId = list(map(lambda x : int(x[-1]), intf.split('-')))
    #       queueId = queueId[0] * 100 + queueId[1] * 10 + r
    #       commands = [
    #         'sudo', 'ovs-vsctl', 'set', 'port', intf, 'qos=@newqos', '--',
    #         '--id=@newqos', 'create', 'qos', 'type=linux-htb', f'queues:{queueId}=@newqueue', '--',
    #         '--id=@newqueue', 'create', 'queue', f'other-config:min-rate={rates[r]}', f'other-config:max-rate={rates[r]}'
    #       ]
    #       run(commands)
    print('__OK__')
    CLI(net)
    net.stop()
  except Exception as e:
    print('ERROR')
    print(e)
    net.stop()


if __name__ == '__main__':
  setLogLevel( 'info' )
  myNetwork()

