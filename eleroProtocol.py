from conf import conf

class eleroProtocol():

    flash_table_encode = [0x08, 0x02, 0x0d, 0x01, 0x0f, 0x0e, 0x07, 0x05, 0x09, 0x0c, 0x00, 0x0a, 0x03, 0x04, 0x0b, 0x06]
    flash_table_decode = [0x0a, 0x03, 0x01, 0x0c, 0x0d, 0x07, 0x0f, 0x06, 0x00, 0x08, 0x0b, 0x0e, 0x09, 0x02, 0x05, 0x04]

# for each command we define a tuple with the type and 2 command bytes
    eleroCmds = { "Check": (0x6A,0x00,0x00),   # ask blind for status
                   "Stop": (0x6A,0x10,0x00),
                   "Up": (0x6A,0x20,0x00),
                   "Tilt": (0x6A,0x24,0x00),   # go to stored position tilt
                   "Down": (0x6A,0x40,0x00),
                   "Int": (0x6A,0x44,0x00),    # go to stored position Intermediate
                   "Async": (0x6A,0xE1,0x00),  # enter asynchronous programming mode (if already bound)
                   "P1": (0x70,0x80,0x00),     # these three commands start the remote/blind binding => P button
                   "P2": (0xF8,0x00,0x00),     # the remote and blind address should be defined in conf.py
                   "P3": (0x78,0x00,0x00),     # they are called as a group via mqtt using the command "Prog"
                   "Pup": (0x78,0x20,0x00),    # up press during remote binding - repeat until blind pauses/stops
                   "Pdown": (0x78,0x40,0x00),  # down press during remote binding - repeat until blind pauses/stops
                   "Pdone": (0x78, 0x00,0x00), # an ack sent automatically when blind sends programming complete
                   "Pdel": (0x45,0x92,0x08)    # delete the binding in the blind for this remote/channel
                }

    eleroState = [
         "Unknown",
         "Top",
         "Bottom",
         "Intermediate",
         "Tilt",
         "Blocking",
         "Overheated",
         "Timeout",
         "StartUp",
         "StartDown",
         "MovingUp",
         "MovingDown",
         "Stopped",
         "Top",       # actually top & tilt
         "Bottom",    # actually bottom & intermediate
         "Off",
         "On",
    ]


    def __init__(self):
        self.gIndex = {} # create a counter for each defined remote
        for remote in conf.remote_addr:
            self.gIndex[''.join('{:02X}'.format(a) for a in remote)]=1

    # translate nibbles using flash_table_decode
    def decode_nibbles(self, msg):
        for i in range(0, len(msg)):
            nh = (msg[i] >> 4) & 0x0F
            nl = msg[i] & 0x0F
    
            dh = self.flash_table_decode[nh]
            dl = self.flash_table_decode[nl]
    
            msg[i] = ((dh << 4) & 0xFF) | ((dl) & 0xFF)

    # subtract a value from each nibble in payload between [start; start+len]
    def sub_r20_from_nibbles(self, msg, r20, start, length):
        for i in range(start, length):
            d = msg[i]
    
            ln = (d - r20) & 0x0F
            hn = ((d & 0xF0) - (r20 & 0xF0)) & 0xFF

            msg[i] = hn | ln

            r20 = (r20 - 0x22) & 0xFF

    # xor the msg bytes with 2 values (decoding)
    def xor_2byte_in_array_dec(self, msg, xor_b0, xor_b1):
        for i in range(0, len(msg), 2):
            msg[i + 0] = msg[i + 0] ^ xor_b0
            msg[i + 1] = msg[i + 1] ^ xor_b1


    #decode a message
    def decode_msg(self, msg):
        self.decode_nibbles(msg)
        self.sub_r20_from_nibbles(msg, 0xFE, 0, 2)       # subtract initial value always 0xFE
        self.xor_2byte_in_array_dec(msg, msg[0], msg[1])
        self.sub_r20_from_nibbles(msg, 0xBA, 2, 8)       # 0xBA is just 0xFE - 2*0x22


    # bit counting for parity
    def count_bits(self, byte):
        ones = 0
        mask = 1
    
        for i in range(0, 8):
            if mask & byte:
                ones += 1
            mask <<= 1

        return ones & 0x01

    # parity calculation
    def calc_parity(self, msg,index=-1, exp=None):
        if (index>=0):  # by default we assume this is done already
            num = (0x00 - (index * 0x708F)) & 0xFFFF
            msg[0]=((num&0xFF00)>>8)
            msg[1]=(num&0xFF)
        p = 0
        for i in range(0, len(msg), 2):

            a = self.count_bits( msg[0 + i] )
            b = self.count_bits( msg[1 + i] )

            p |= a ^ b
            p <<= 1
        msg[7] = ((p << 3)) & 0xFF

    # add a value to each nibble in payload between [start; start+len]
    def add_r20_to_nibbles(self, msg, r20, start, length):
        for i in range(start, length):
            d = msg[i]
    
            ln = (d - r20) & 0x0F
            hn = ((d & 0xF0) - (r20 & 0xF0)) & 0xFF

            msg[i] = hn | ln
    
            r20 = (r20 - 0x22) & 0xFF

    # add values payload bytes
    def add_r20_to_nibbles(self, msg, r20, start, length):
        for i in range(start, length):
            d = msg[i]

            ln = (d + r20) & 0x0F
            hn = ((d & 0xF0) + (r20 & 0xF0)) & 0xFF

            msg[i] = hn | ln

            r20 = (r20 - 0x22) & 0xFF

    # xor bytes in an array with 2 values (encoding - skip first 2)
    def xor_2byte_in_array_enc(self, msg, xor_b0, xor_b1):
        for i in range(2, len(msg), 2):
            msg[i + 0] = msg[i + 0] ^ xor_b0
            msg[i + 1] = msg[i + 1] ^ xor_b1

    # encode the nibbles using the table
    def encode_nibbles(self, msg):
        for i in range(0, len(msg)):
            nh = (msg[i] >> 4) & 0x0F
            nl = msg[i] & 0x0F

            dh = self.flash_table_encode[nh]
            dl = self.flash_table_encode[nl]
    
            msg[i] = ((dh << 4) & 0xFF) | ((dl) & 0xFF)

    # encode a message
    def encode_msg(self, msg):
        xor_val0 = msg[0]
        xor_val1 = msg[1]

        self.calc_parity(msg)
        self.add_r20_to_nibbles(msg, 0xFE, 0, 8)
        self.xor_2byte_in_array_enc(msg, xor_val0, xor_val1)
        self.encode_nibbles(msg)

    def interpretMsg(self, msg):
        try:
            length=msg[1]
            cnt=msg[2]
            typ=msg[3]
            chl=msg[7]
            src=[msg[8],msg[9],msg[10]]
            bwd=[msg[11],msg[12],msg[13]]
            fwd=[msg[14],msg[15],msg[16]]
            dests=[]
            for i in range(msg[17]):
                if (typ>0x60):
                    dests.append([msg[18+i*3],msg[19+i*3],msg[20+i*3]])
                    destsLen=msg[17]*3
                else:
                    dests.append([msg[18+i]])
                    destsLen=msg[17]
            payload=msg[20+destsLen:28+destsLen]
            self.decode_msg(payload)
            if (msg[-2]>127):
                rssi=(msg[-2]-256)/2-74
            else:
                rssi=(msg[-2])/2-74
            lqi=msg[-1]&0x7F
            crc=msg[-1]>>7
            return(length,cnt,typ,chl,src,bwd,fwd,dests,payload,rssi,lqi,crc)
        except Exception as e:
            print("badpkt="+''.join('{:02X}:'.format(a) for a in msg))
            return(0,0,0,0,0,0,0,0,0,0,0,0)
    

    # all messages are generated with this so it's a bit of a mess
    def generate_msg(self, addr, index, blind_id, command):

        msg=[]
        hexcmd=self.eleroCmds[command][0]
        if (hexcmd<0x60):
            msg.append(0x1B)          # msg_len
        else:
            msg.append(0x1D)          # msg_len
        msg.append(index)             # pck cnt
        msg.append(hexcmd)            # typ of command
        msg.append(0x10)              # pck_inf2 = always 0x10?
        if (command[0]=="P"):
            msg.append(0x00)          # hop_info = 0
        else:
            msg.append(0x05)          # hop_info = 5
        msg.append(0x01)              # sys_addr = 1
        msg.append(blind_id[3])
    
        msg.append(addr[0])   # source addr[0]
        msg.append(addr[1])   # source addr[1]
        msg.append(addr[2])   # source addr[2]
        msg.append(addr[0])   # backward addr[0]
        msg.append(addr[1])   # backward addr[1]
        msg.append(addr[2])   # backward addr[2]
        msg.append(addr[0])   # forward addr[0]
        msg.append(addr[1])   # forward addr[1]
        msg.append(addr[2])   # forward addr[2]

        msg.append(0x01)          # dest_count = 1
        if (hexcmd < 0x60):
            msg.append(blind_id[3])
            msg.append(0x00)
            msg.append(0x01) # not sure about this
        elif (command=='P1'):        # special case - destination unknown
            msg.append(blind_id[3])  # dest = channel        
            msg.append(0x00)
            msg.append(0x00)
            msg.append(0x00)
            msg.append(0x03) # not sure about this
        elif (command=="P2"):
            msg.append(blind_id[0])  # dest = 3 byte address
            msg.append(blind_id[1])
            msg.append(blind_id[2])
            payload=[0]*10           # empty unecoded payload
        else:
            msg.append(blind_id[0])  # dest = 3 byte address
            msg.append(blind_id[1])
            msg.append(blind_id[2])
            if (command=='P3'):
                msg.append(0x04)
                msg.append(0x01) 
            elif (command=='Pdone'):
                msg.append(0x08)
                msg.append(0x01) 
            elif ((command=='Pup') or (command=='Pdown')):
                msg.append(0x00)
                msg.append(0x01) 
            else:
                msg.append(0x00)
                msg.append(0x04) # not sure about this

        if (command!="P2"):
            code = (0x00 - (index * 0x708F)) & 0xFFFF
            payload=[]
            payload.append((code >> 8) & 0xFF)
            payload.append(code & 0xFF)
            payload.append(self.eleroCmds[command][1])   # actual command
            payload.append(self.eleroCmds[command][2])
            payload.append(0)
            if (command=='P1') or (command=='P3'):
                payload.append(2)
            else:
                payload.append(0)
            payload.append(0)
            payload.append(0)
            self.encode_msg(payload);

        return(msg + payload)

    def construct_msg(self, remote_addr,blind_addr,command):

        rIndex=''.join('{:02X}'.format(a) for a in remote_addr)
        msg=self.generate_msg(remote_addr, self.gIndex[rIndex], blind_addr, command)
        self.gIndex[rIndex]=(self.gIndex[rIndex]+1)&0xFF
        
        return(msg)

    # for most commands we'll use the first remote which "knows" the blind
    # but for programming we want the last - so we can "learn" an existing blind on a new software remote    
    def getTarget(self, blind, firstOne=True):
        targetBlind=0
        targetRemote=0
        remIndex=0
        for remote in conf.remote_blind_id:
            for b in remote:
                baddr=''.join('{:02X}:'.format(a) for a in b[0:3])
                if (baddr == blind):
                    targetBlind=b
                    targetRemote=conf.remote_addr[remIndex]
            if (firstOne and targetBlind):
                 break # retrun first match
            remIndex+=1
        return(targetBlind,targetRemote)
