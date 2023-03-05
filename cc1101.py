# a cc1101 driver class for both RPi and esp32.
# It might be better to split it but at least the lots of 
# magic numbers (cc1101 configuration, etc) are in one place
import time
import os
from conf import conf

class cc1101():

    def gdo2Int(self,Pin):
        self.pktRec=True

    def __init__(self, spibus,spics,speed,gdo0,gdo2):

        if (os.uname()[0]=='esp32'):
            from machine import Pin, SPI
            self.gdo0=Pin(gdo0, Pin.IN)
            self.gdo2=Pin(gdo2, Pin.IN)
            self.gdo2.irq(trigger=Pin.IRQ_FALLING, handler=self.gdo2Int)
            self.spi = SPI(spibus, baudrate=speed)
            self.cs=Pin(spics, Pin.OUT,value=1)
            self.writeCmd = self.writeCmdEsp
            self.writeReg = self.writeRegEsp
            self.writeBuf = self.writeBufEsp
            self.readReg  = self.readRegEsp
            self.readBuf  = self.readBufEsp
            self.pinVal   = self.pinValEsp
        else:
            import spidev
            import RPi.GPIO as GPIO
            self.gdo0 = gdo0
            self.gdo2 = gdo2
            self.spi = spidev.SpiDev(spibus,spics)
            self.spi.max_speed_hz = speed
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.gdo0, GPIO.IN)
            GPIO.setup(self.gdo2, GPIO.IN)
            GPIO.add_event_detect(self.gdo2, GPIO.FALLING, callback=self.gdo2Int)
            self.writeCmd = self.writeCmdRpi
            self.writeReg = self.writeRegRpi
            self.writeBuf = self.writeBufRpi
            self.readReg  = self.readRegRpi
            self.readBuf  = self.readBufRpi
            self.pinVal   = self.pinValRpi
            self.GPIO     = GPIO

        self.pktRec=False

        self.writeCmd(0x30)
        self.writeCmd(0x36)
    
        self.writeReg(0x0B, 0x08)
        self.writeReg(0x0C, 0x00)
        self.writeReg(0x0D, 0x21)
        self.writeReg(0x0E, 0x71) # 71 may need tweaking
        self.writeReg(0x0F, 0xC0) # 7A may need tweaking
        self.writeReg(0x10, 0x7B)
        self.writeReg(0x11, 0x83)
        self.writeReg(0x12, 0x13) # MDMCFG2 Modem Configuration 0x13
        self.writeReg(0x13, 0x52)
        self.writeReg(0x14, 0xF8)
        self.writeReg(0x0A, 0x00)
        self.writeReg(0x15, 0x43)
        self.writeReg(0x21, 0xB6)
        self.writeReg(0x22, 0x10)
        self.writeReg(0x18, 0x18)
        self.writeReg(0x17, 0x3F)
        self.writeReg(0x19, 0x1D)
        self.writeReg(0x1A, 0x1F)
        self.writeReg(0x1B, 0xC7)
        self.writeReg(0x1C, 0x00)
        self.writeReg(0x1D, 0xB2)
        self.writeReg(0x23, 0xEA)
        self.writeReg(0x24, 0x2A)
        self.writeReg(0x25, 0x00)
        self.writeReg(0x26, 0x1F)
        self.writeReg(0x29, 0x59)
        self.writeReg(0x2C, 0x81)
        self.writeReg(0x2D, 0x35)
        self.writeReg(0x2E, 0x09)
        self.writeReg(0x00, 0x06)
        self.writeReg(0x02, 0x09)
        self.writeReg(0x07, 0x8C)  # only pkts that pass CRC check
        self.writeReg(0x08, 0x45)
        self.writeReg(0x09, 0x00)
        self.writeReg(0x06, 0x3C)
        self.writeReg(0x04, 0xD3)
        self.writeReg(0x05, 0x91)
        self.writeReg(0x7E, 0xC2)
        for i in range(8):
            self.writeReg(0x3E, 0xC0) # full power
        self.writeCmd(0x34)

        print("check",self.readReg(0x8E))
        print("Waiting for clear channel...")
        while (  self.pinVal(self.gdo0) == 0 ):
            time.sleep(0.0001)
            print(".",end='')
        print("channel cleared");

    def transmit(self,msg):

        self.writeCmd(0x36)
        self.writeCmd(0x3A)
        self.writeCmd(0x3B)
        self.writeCmd(0x34)

        start=time.time_ns()
        while (  self.pinVal(self.gdo0) == 0 ) and ((time.time_ns()-start)<50000000):
             time.sleep(0.005)

        if ( self.pinVal(self.gdo0) == 0):
            print("TIMEOUT")
        else:
            self.writeBuf([0x7F]+msg)

        time.sleep(0.00004)
        self.writeCmd(0x35)

        start=time.time_ns()
        while (self.readReg(0xF5)!=0x13) and ((time.time_ns()-start)<50000000):
            time.sleep(0.005)
        if conf.rawTrace:
            print("sent: ",''.join('{:02X}:'.format(a) for a in msg),self.readReg(0xF5))

    def checkBuffer(self):
        data=None
        if (self.pktRec):
            time.sleep(0.00002)
            self.pktRec=False
            bytes_in_fifo = self.readReg(0xFB)
            if  (bytes_in_fifo>=20) and (bytes_in_fifo<30) and conf.rawTrace:
                d=self.readBuf(0xFF,bytes_in_fifo+1)
                print(time.time(),''.join('{:02X}:'.format(a) for a in d))
            if (bytes_in_fifo>=30):
                data=self.readBuf(0xFF,bytes_in_fifo+1)
                if conf.rawTrace:
                    print(time.time(),''.join('{:02X}:'.format(a) for a in data))
            self.writeCmd(0x36)
            self.writeCmd(0x3A)
            self.writeCmd(0x3B)
            self.writeCmd(0x34)
        return(data)

    def writeCmdRpi(self,cmd):
        self.spi.writebytes([cmd])
        time.sleep(0.00004)

    def writeCmdEsp(self,cmd):
        self.cs(0)
        self.spi.write(bytearray([cmd]))
        self.cs(1)
        time.sleep(0.00004)

    def writeRegRpi(self,reg,val):
        self.spi.xfer([reg, val])
        time.sleep(0.00002)

    def writeRegEsp(self,reg,val):
        self.cs(0)
        self.spi.write(bytearray([reg,val]))
        self.cs(1)
        time.sleep(0.00002)

    def writeBufRpi(self,msg):
        self.spi.xfer2(msg)

    def writeBufEsp(self,msg):
        self.cs(0)
        buf=bytearray(msg)
        self.spi.write(buf)
        self.cs(1)

    def readRegRpi(self,reg):
        return(self.spi.xfer([reg,0])[1])

    def readRegEsp(self,reg):
        self.cs(0)
        result=self.spi.read(2, reg)[1]
        self.cs(1)
        return(result)
    
    def readBufRpi(self,addr,length):
        reader = [addr]*(length)
        return(self.spi.xfer2(reader))

    def readBufEsp(self,addr,length):
        self.cs(0)
        buf=bytearray([addr]*length)
        self.spi.write_readinto(buf, buf)
        self.cs(1)
        return(buf)

    def pinValRpi(self,pin):
        return(self.GPIO.input(pin))

    def pinValEsp(self,pin):
        return(pin())

