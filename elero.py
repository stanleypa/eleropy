#!/usr/bin/env python3
# the main executable for RPi
import time
import os
import paho.mqtt.client as mqtt


from conf import conf
from cc1101 import cc1101
from eleroProtocol import eleroProtocol

# mqtt
# The callback for when the client receives a CONNACK response from the server.
def on_connect(client, userdata, flags, rc):
    print("Connected to MQTT with result code "+str(rc),flush=True)
    client.subscribe(conf.mqtt_command_topic+"#")

# The callback for when a PUBLISH message is received from the server.
def on_message(client, userdata, msg):

    command=msg.payload.decode("utf-8").rstrip()
    print(msg.topic+" "+command,flush=True)
    blind=(msg.topic.split('/')[2])+":"
    first=(command[0]!='P') # for programming commands we want the last remote that knows the blind
    targetBlind,targetRemote = elero.getTarget(blind,first)
    if (targetBlind):
        if (command == "Prog"):
            txmsg=elero.construct_msg(targetRemote,targetBlind,'P1')
            for i in range(conf.retrans):
                radio.transmit(txmsg)
            print("sent P1 to "+blind,flush=True)
            # any blinds in Async mode will send their address as a 0xD4 type message
            # but for simplicity we'll ignore that and use the address/channel in conf.py
            time.sleep(2.1) 
            txmsg=elero.construct_msg(targetRemote,targetBlind,'P2')
            for i in range(conf.retrans):
                radio.transmit(txmsg)
            print("sent P2 to "+blind,flush=True)
            time.sleep(0.5) 
            txmsg=elero.construct_msg(targetRemote,targetBlind,'P3')
            for i in range(conf.retrans):
                radio.transmit(txmsg)
            print("sent P3 to "+blind,flush=True)
        else:
            txmsg=elero.construct_msg(targetRemote,targetBlind,command)
            print("sending: ",''.join('{:02X}:'.format(a) for a in targetRemote),targetBlind[3],''.join('{:02X}:'.format(a) for a in targetBlind[0:3]), command)
            for i in range(conf.retrans):
                radio.transmit(txmsg)
            print("sent "+command+" to "+blind,flush=True)
    else:
        print(blind+" blind not found",flush=True)


# main
radio=cc1101(spibus=conf.spibus,spics=conf.spics,speed=conf.speed,gdo0=conf.gdo0,gdo2=conf.gdo2)
elero=eleroProtocol()


client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message
client.connect(conf.mqtt_addr, conf.mqtt_port, conf.mqtt_alive)
client.loop_start()

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
            print("pay="+''.join('{:02X}:'.format(a) for a in payload),flush=True)

            if (typ==0xD4):  # responses during programming - we only handle 1 case:
                if (sum(dests[0])==0):  # programming complete
                    txmsg=elero.construct_msg(fwd,src+[chl],'Pdone')
                    print("sending: ",''.join('{:02X}:'.format(a) for a in fwd),chl,''.join('{:02X}:'.format(a) for a in src), "Pdone")
                    for i in range(conf.retrans):
                        radio.transmit(txmsg)
                    print("sent Pdone",flush=True)

            if (typ==0xCA):
                topic=conf.mqtt_status_topic+"{:02X}:{:02X}:{:02X}".format(src[0],src[1],src[2])
                try:
                    client.publish(topic, elero.eleroState[payload[6]])
                except Exception as e:
                    print(str(e),payload[6])
                # only makes sense to post rssi for the actual transmitter (bwd)
                topic=conf.mqtt_rssi_topic+"{:02X}:{:02X}:{:02X}".format(bwd[0],bwd[1],bwd[2])
                client.publish(topic, "{:.1f}".format(rssi))
    else:
        time.sleep(conf.sleepTime) # we're sharing the system on the RPi so don't busy wait

    # check blind status - one per remote per second at the start of the checkFreq cycle
    checkCounter=int(time.time())%conf.checkFreq
    if (checkCounter != checkChannel) and (checkCounter < len(conf.remote_blind_id[0])):
        checkChannel=checkCounter
        remoteIndex=0
        for remote in conf.remote_blind_id:
            if remote[checkChannel][3]>0:
                msg=elero.construct_msg(conf.remote_addr[remoteIndex],remote[checkChannel],"Check")
                radio.transmit(msg) # only one transmit as we'll repeat next cycle
            remoteIndex+=1
    
