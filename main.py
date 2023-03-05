# the main executable for esp32 
# should be started/imported in boot.py
# it assumes boot.py initialises wifi

import time
import os
import gc

from conf import conf
from cc1101 import cc1101
from eleroProtocol import eleroProtocol
from mqtt import MQTTClient
from machine import WDT


# mqtt
# The callback for when a PUBLISH message is received from the server.
def on_message(topic, msg):

    command=msg.decode("utf-8").rstrip()
    topic=topic.decode("utf-8").rstrip()
    print(topic+" "+command)
    blind=(topic.split('/')[2])+":"
    first=(command[0]!='P') # for programming commands we want the last remote that knows the blind
    targetBlind,targetRemote = elero.getTarget(blind,first)
    if (targetBlind):
        if (command == "Prog"):
            txmsg=elero.construct_msg(targetRemote,targetBlind,'P1')
            for i in range(conf.retrans):
                radio.transmit(txmsg)
            print("sent P1 to "+blind)
            # any blinds in Async mode will send their address as a 0xD4 type message
            # but for simplicity we'll ignore that and use the address/channel in conf.py
            time.sleep(2.1)
            txmsg=elero.construct_msg(targetRemote,targetBlind,'P2')
            for i in range(conf.retrans):
                radio.transmit(txmsg)
            print("sent P2 to "+blind)
            time.sleep(0.5)
            txmsg=elero.construct_msg(targetRemote,targetBlind,'P3')
            for i in range(conf.retrans):
                radio.transmit(txmsg)
            print("sent P3 to "+blind)
        else:
            txmsg=elero.construct_msg(targetRemote,targetBlind,command)
            print("sending: ",''.join('{:02X}:'.format(a) for a in targetRemote),targetBlind[3],''.join('{:02X}:'.format(a) for a in targetBlind[0:3]), command)
            for i in range(conf.retrans):
                radio.transmit(txmsg)
            print("sent "+command+" to "+blind)
    else:
         print(blind+" blind not found")


# main
# enable watchdog timer.
wdt = WDT(timeout=conf.wdtTimeout)
wdt.feed()

radio=cc1101(spibus=conf.spibus,spics=conf.spics,speed=conf.speed,gdo0=conf.gdo0,gdo2=conf.gdo2)
elero=eleroProtocol()

client = MQTTClient("cc1101esp32",conf.mqtt_addr, conf.mqtt_port, keepalive=conf.mqtt_alive)
client.set_callback(on_message)
client.connect()
client.subscribe(conf.mqtt_command_topic+"#")

lastCheck=time.time()
checkChannel=0

while True:
    data=radio.checkBuffer()
    if (data):
        (length,cnt,typ,chl,src,bwd,fwd,dests,payload,rssi,lqi,crc)=elero.interpretMsg(data)
        if (length>0):  # length 0 => interpretation failed 
            print("len= {:d}, cnt= {:d}, typ={:02X}, chl={:d}".format(length,cnt,typ,chl), end=',')
            print('src=[{:02X}{:02X}{:02X}]'.format(src[0],src[1],src[2]),end=',')
            print('bwd=[{:02X}{:02X}{:02X}]'.format(bwd[0],bwd[1],bwd[2]),end=',')
            print('fwd=[{:02X}{:02X}{:02X}]'.format(fwd[0],fwd[1],fwd[2]),end=' - ')
            print('des={:d}'.format(len(dests)),end=':')
            for dest in dests:
                if (len(dest)>1):
                    print(':[{:02X}{:02X}{:02X}]'.format(dest[0],dest[1],dest[2]),end=',')
                else:
                    print(':[{:d}]'.format(dest[0]),end=',')
            print("rssi={:.1f},lqi={:d},crc={:d}".format(rssi,lqi,crc),end=', ')
            print("pay="+''.join('{:02X}:'.format(a) for a in payload))

            if (typ==0xD4):  # responses during programming - we only handle 1 case:
                if (sum(dests[0])==0):  # programming complete
                    txmsg=elero.construct_msg(fwd,src+[chl],'Pdone')
                    print("sending: ",''.join('{:02X}:'.format(a) for a in fwd),chl,''.join('{:02X}:'.format(a) for a in src), "Pdone")
                    for i in range(conf.retrans):
                        radio.transmit(txmsg)
                    print("sent Pdone")

            if (typ==0xCA):
                topic=conf.mqtt_status_topic+"{:02X}:{:02X}:{:02X}".format(src[0],src[1],src[2])
                try:
                    client.publish(topic, elero.eleroState[payload[6]])
                    wdt.feed()
                except Exception as e:
                    print(str(e),payload[6])
                # only makes sense to post rssi for the actual transmitter (bwd)
                topic=conf.mqtt_rssi_topic+"{:02X}:{:02X}:{:02X}".format(bwd[0],bwd[1],bwd[2])
                client.publish(topic, "{:.1f}".format(rssi))

    client.check_msg()
    checkCounter=int(time.time())%conf.checkFreq
    # garbage collection once every checkFreq seconds
    if  (checkCounter ==16) and (checkCounter != checkChannel):
        checkChannel=checkCounter
        gc.collect()
    # check blind status - one per remote per second at the start of the checkFreq cycle
    if (checkCounter != checkChannel) and (checkCounter < len(conf.remote_blind_id[0])):
        checkChannel=checkCounter
        remoteIndex=0
        for remote in conf.remote_blind_id:
            if remote[checkChannel][3]>0:
                msg=elero.construct_msg(conf.remote_addr[remoteIndex],remote[checkChannel],"Check")
                radio.transmit(msg) # just one transmit - we'll check again in checkFreq seconds
            remoteIndex+=1
    
