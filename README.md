# Trabalho Semestral MATA59 T02 <br> Redes de Computadores 2022.2

**Grupo 10**

- Daniel Carneiro
- John Lemos
- Leon Santos
- Rodrigo Peixoto
- Yago Martins

---

### Neste documento, ser�o descritas as etapas de desenvolvimento para implementa��o de uma rede corporativa, conforme especifica��es do roteiro disponibilizado.

1. [Vers�es Utilizadas](#Versoes)
1. [Topologia](#Topologia)
2. [SDN](#SDN)
3. [Testes da Interface REST](#REST)
4. [Testes Funcionais (Execu��o do c�digo)](#Testes)

## Vers�es utilizadas <a name="Versoes"/>

Para realiza��o deste trabalho, a m�quina virtual que j� continha o Mininet **n�o** foi utilizada. Devido a incompatibilidades referentes a vers�o do Python e problemas com autoriza��es para alterar arquivos do sistema, o grupo optou por utilizar uma outra vers�o.
As vers�es utilizadas est�o dispostas a seguir:

- VM Ubuntu 22.04 (atrav�s do Virtual Box)
- Python 3.8.10
- Mininet 2.3.1b1
- Ryu 4.34

Caso no momento da execu��o do controlador, explicada mais a frente na se��o [Testes Funcionais (Execu��o do c�digo)](#Testes),  seja exibido algum erro referente ao Eventlet, recomenda-se a desinstalar a vers�o atual e instalar a vers�o 0.30.2 do pacote, atrav�s dos comandos a seguir:
```console
pip uninstall eventlet
pip install eventlet==0.30.2
```

## Topologia <a name="Topologia "/>

![Topologia requisitada](https://drive.google.com/uc?export=view&id=13xOWqkC8LU046XoPo-XdJBbqqroRUaaN)<p align = "center">Topologia especificada</p>

Implementou-se no Miniedit, interface visual do Mininet, a rede descrita nas especifica��es do trabalho. Foram colocados os hosts e switches conforme o diagrama disponibilizado e ent�o feitos os links (conex�es).

![Topologia implementada](https://drive.google.com/uc?export=view&id=13xromADgS_3FzvsjK3g9WBujLNjIjAxi)
<p align = "center">Topologia implementada no Miniedit</p>

Optou-se por realizar configura��es mais avan�adas atrav�s de c�digo. Portanto, ap�s realizar as conex�es das estruturas da rede, exportou-se o script em Python da topologia n�vel 2. No arquivo "topo.py", definiu-se endere�os MAC personalizados para cada um dos hosts (a fim de facilitar o processo de debug) e os endere�os de IP, conforme as especifica��es.


```Python
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
```
<p align = "center">Trecho do c�digo "topo.py"</p>

Defini��o do controlador RYU para os todos os switches:

```Python
  try:
    for s in net.switches:
      run(['sudo', 'ovs-vsctl', 'set-controller', str(s), 'tcp:127.0.0.1:6653'])
```

Cria��o das filas de controle de banda:
```Python
rates = [int(x) for x in [1e6, 10e6, 20e6]]
    for s in net.switches:
      intfs = list(net.get(str(s)).intfs.values())
      for i in range(1, len(intfs)):
        for r in range(len(rates)):
          intf = str(intfs[i])
          queueId = list(map(lambda x : int(x[-1]), intf.split('-')))
          queueId = queueId[0] * 100 + queueId[1] * 10 + r
          commands = [
            'sudo', 'ovs-vsctl', 'set', 'port', intf, 'qos=@newqos', '--',
            '--id=@newqos', 'create', 'qos', 'type=linux-htb', f'queues:{queueId}=@newqueue', '--',
            '--id=@newqueue', 'create', 'queue', f'other-config:min-rate={rates[r]}', f'other-config:max-rate={rates[r]}'
          ]
          run(commands)
```


Com a topologia devidamente implementada, iniciou-se o desenvolvimento da aplica��o SDN de orquestra��o.

## SDN <a name="SDN"/>

Para implementa��o da aplica��o de controle de acesso SDN, utilizou-se o controlador RYU para realizar o controle dos switches e envio das regras OpenFlow.
Os principais requisitos que deveriam ser implementados na rede est�o listados a seguir:
 - Controle de acesso entre hosts de diferentes seguimentos.
	 - Com a devida implementa��o de preced�ncias de prioridade.
 - Permiss�o de acesso entre hosts de um mesmo segmento.
 - Cadastros de Hosts.
 - Controle de acesso de hosts com base no dia e no hor�rio.
 - Controle da taxa de download por segmento.

Todas as regras foram implementadas no arquivo "App.py". Algumas das regras implementadas ser�o descritas com mais detalhes nesta documenta��o, a fim de detalhar mais a parte de prioridades.  

### Cadastros de segmentos de rede e hosts
```Python
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
```





### Controle de acesso de hosts por seguimento

```Python
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
```
Regras de permiss�o com um mesmo n�vel de prioridade de uma regra de bloqueio tem prefer�ncia. 

Al�m disso, para determinar se uma comunica��o pode ser estabelecida, verifica-se a prioridade da regra de bloqueio ou libera��o, implementada conforme tabela abaixo:

|Prioridade | Tipo de conex�o  |
|:---:|:---:|
| 1 | Host - Host |
| 2 | Host - Segmento|
| 2 | Segmento - Segmento|

Onde 1 representa a maior prioridade e 3 a menor prioridade.

**Exemplos**
> Um libera��o de comunica��o host-host tem prioridade em rela��o a um bloqueio feito no segmento onde eles se localizam

> Caso hajam duas regras, uma de bloqueio e outra de permiss�o para a comunica��o visitante1-internet, a comunica��o ser� liberada, pois regras de libera��o com a mesma prioridade prevalecem.




## Testes da Interface REST  <a name="REST"/>

Para realiza��o de testes da rede SDN, a equipe optou por utilizar o Postman, uma plataforma que auxilia no processo de desenvolvimento e testes de APIs.
No Postman, foi criada uma cole��o de requisi��es, a fim de atender a todas as situa��es propostas no roteiro do trabalho, dentre elas:

- Cadastro de segmento de rede e hosts.
- Listagem dos segmentos cadastrados.
- Remo��o de hosts e segmentos de rede.
- Cria��o de regras de controle de acesso b�sica por segmentos.
- Cria��o de regra de controle de acesso b�sica por hosts.
	- Com a devida valida��o das prioridades.
- Cria��o de regra de controle de acesso b�sica por host e segmento.
- Cria��o de regras de acesso com restri��o de data e hor�rio.
- Cria��o de regras de controle de acesso com restri��o de banda de download.
- Listagem das regras de controle existente.
- Remo��o de regras de controle.

Portanto, para cada um dos cen�rios exemplos acima, implementou-se no controlador os comandos a serem realizados ao receber cada uma das requisi��es.
```Python
 @route('', '/nac/segmentos/', methods=['GET'])
  def r2(self, req, **kwargs):
    try:
      hostsBySegs = self.simple_switch_app.hostsBySegs
      body = json.dumps(hostsBySegs)
      return Response(content_type='application/json', body=body)
    except:
      return Response(status=500)
```
<p align = "center">C�digo da API para o comando de listagem dos segmentos</p>

O arquivo da cole��o est� disposto neste reposit�rio e pode ser importado na aplica��o para agilizar o processo de testes em outras m�quinas.

## Testes Funcionais (Execu��o do C�digo) <a name="Testes"/>

#### Atrav�s do passo a passo a seguir, � poss�vel executar o Mininet e a aplica��o controladora para testar se a rede se comporta conforme o esperado.

1. Com o terminal aberto na pasta base do reposit�rio, utilizar o comando � seguir para limpeza do Mininet.
	```console
	sudo mn -c
	```

2. Iniciar o arquivo de topologia.
	```console
	clear && sudo python3 topo.py
	```

3. Em outro terminal, tamb�m na pasta base do reposit�rio, iniciar a aplica��o de controle.
	 ```console
	 clear && ryu-manager app.py
	 ```

4. Com os dois terminais executando o Mininet e a aplica��o controladora, utilizar a cole��o implementada no Postman para enviar requisi��es.
	- � poss�vel monitorar o recebimento das requisi��es atrav�s do terminal do controlador.
	- Tamb�m � poss�vel monitorar a conex�o de um host com o outro realizando pings atrav�s do Mininet:
		 ```console
		visitante1 ping internet
		```
	 

