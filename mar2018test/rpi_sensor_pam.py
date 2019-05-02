#!/usr/bin/env python

from __future__ import print_function
from casperfpga import i2c_volt,i2c_bar,i2c_eeprom,i2c_motion,i2c_sn,i2c_temp,i2c_gpio,i2c
import numpy as np,time,logging,struct,random,sys,time,argparse,Queue,threading

def db2gpio(ae,an):
    assert ae in range(0,16)
    assert an in range(0,16)
    ae = 15 - ae
    an = 15 - an
    val_str = '{0:08b}'.format((ae << 4) + an)
    val = int(val_str,2)
    return val

def gpio2db(val):
    assert val in range(0,256)
    val_str = '{0:08b}'.format(val)
    ae = int(val_str[0:4],2)
    an = int(val_str[4:8],2)
    return 15-ae, 15-an

def dc2dbm(val):
    assert val>=0 and val<=3.3, "Input value {} out range of 0-3.3V".format(val)
    slope = 27.31294863
    intercept = -55.15991678
    res = val * slope + intercept
    return res

def number(s):
    if s.startswith('0b'):
        val=int(s,2)
    elif s.startswith('0x'):
        val=int(s,16)
    else:
        val=int(s)
    return val

if __name__ == "__main__":

    p = argparse.ArgumentParser(description='Test PAM module. Use this script when RPI directly connects to Full Control Breakout board for HERA. Before trying this script, please install pigpio first on your raspberry pi and run sudo pigpiod.',
epilog="""Examples:
python rpi_sensor_pam.py --i2c 1 --atten
python rpi_sensor_pam.py --i2c 1 --atten 7 13
python rpi_sensor_pam.py --i2c 1 --gpio
python rpi_sensor_pam.py --i2c 1 --gpio 0xff
python rpi_sensor_pam.py --i2c 1 --rom
python rpi_sensor_pam.py --i2c 1 --rom 'Hello world!'
python rpi_sensor_pam.py --i2c 1 --volt
python rpi_sensor_pam.py --i2c 1 --id""",
formatter_class=argparse.RawDescriptionHelpFormatter)

    p.add_argument('--i2c', dest='i2c', type=int, metavar=('I2C_NAME'), choices=[1,2,3], required=True,
                help='Specify the name the i2c bus.')
    p.add_argument('--baud', dest='baud', type=int, metavar=('I2C_BAUD_RATE'), default=10000,
                help='Specify the baud rate of the i2c bus.')
    p.add_argument('--rom', nargs='?', metavar=('TEXT'), const='', help='Test EEPROM. Leave parameter empty to read ROM. Add text to write ROM.')
    p.add_argument('--id',action='store_true', default=False,help='Print ID.')
    p.add_argument('--volt', action='store_true', default=False, help='Print shunt voltage, shunt current and bus voltage.')
    p.add_argument('--power',action='store_true', default=False, help='Print East and North power in dBm.')
    p.add_argument('--probe', action='store_true', default=False, help='Detect devices on the bus')
    g=p.add_mutually_exclusive_group()
    g.add_argument('--gpio', nargs='?', const=-1, type=number, metavar=('VALUE'), help='Test GPIO. Leave parameter empty to read gpio. Add value to write gpio.')
    g.add_argument('--atten', nargs='*', metavar=('EAST','NORTH'), help='Specify attenuation of East and North pole, 0-15 dB with 1 dB step. Leave parameter empty to read attenuation.')
    args = p.parse_args()

    #      0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f
    # 00:          -- -- -- -- -- -- -- -- -- 0c -- -- --
    # 10: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
    # 20: 20 21 -- -- -- -- -- -- -- -- -- -- -- -- -- --
    # 30: -- -- -- -- -- -- 36 -- -- -- -- -- -- -- -- --
    # 40: 40 -- -- -- 44 -- -- -- -- -- -- -- -- -- 4e --
    # 50: 50 51/52 -- -- -- -- -- -- -- -- -- -- -- -- --
    # 60: -- -- -- -- -- -- -- -- -- 69 -- -- -- -- -- --
    # 70: -- -- -- -- -- -- -- 77

    ACCEL_ADDR = 0X69
    MAG_ADDR = 0x0c
    BAR_ADDR = 0x77
    VOLT_FEM_ADDR = 0x4e
    VOLT_PAM_ADDR = 0x36
    ROM_FEM_ADDR = 0x51
    ROM_PAM_ADDR = 0x52
    TEMP_ADDR = 0x40
    SN_ADDR = 0x50
    INA_ADDR = 0x44
    GPIO_PAM_ADDR = 0x21
    GPIO_FEM_ADDR = 0x20

    ANT1_I2C_GPIO_SDA_PIN = 4
    ANT1_I2C_GPIO_SCL_PIN = 14
    ANT2_I2C_GPIO_SDA_PIN = 6
    ANT2_I2C_GPIO_SCL_PIN = 12
    ANT3_I2C_GPIO_SDA_PIN = 16
    ANT3_I2C_GPIO_SCL_PIN = 26

    # RPI I2C interface
    i2clist = [[ANT1_I2C_GPIO_SDA_PIN,ANT1_I2C_GPIO_SCL_PIN],
               [ANT2_I2C_GPIO_SDA_PIN,ANT2_I2C_GPIO_SCL_PIN],
               [ANT3_I2C_GPIO_SDA_PIN,ANT3_I2C_GPIO_SCL_PIN]]
    bus = i2c.I2C_PIGPIO(i2clist[args.i2c-1][0], i2clist[args.i2c-1][1], args.baud)

    if args.id:
        sn=i2c_sn.DS28CM00(bus,SN_ADDR)
        val=sn.readSN()
        print('The id of the ID chip is: {}'.format(val))

    if args.atten!=None:
        gpio=i2c_gpio.PCF8574(bus,GPIO_PAM_ADDR)
        if len(args.atten)>0:
            ve=int(args.atten[0])
            vn=int(args.atten[1])
            gpio.write(db2gpio(ve,vn))
        else:
            val=gpio.read()
            ve,vn=gpio2db(val)
            print('{}, {}'.format(ve,vn))
    elif args.gpio!=None:
        gpio=i2c_gpio.PCF8574(bus,GPIO_PAM_ADDR)
        if args.gpio<0:
            print('0b{:08b}'.format(gpio.read()))
        else:
            gpio.write(args.gpio)

    if args.rom!=None:
        rom=i2c_eeprom.EEP24XX64(bus,ROM_PAM_ADDR)
        if args.rom=='':
            print(rom.readString())
        else:
            rom.writeString(args.rom)

    if args.power:
        volt=i2c_volt.MAX11644(bus,VOLT_PAM_ADDR)
        volt.init()
        vp1,vp2=volt.readVolt()
        loss = 9.8
        print('{},{},{}'.format(vp1,dc2dbm(vp1), dc2dbm(vp1)+loss))
        print('{},{},{}'.format(vp2,dc2dbm(vp2), dc2dbm(vp1)+loss))

    if args.volt:
        # full scale 909mA
        ina=i2c_volt.INA219(bus,INA_ADDR)
        ina.init()
        vshunt = ina.readVolt('shunt')
        vbus = ina.readVolt('bus')
        res = 0.1
        print('{},{},{}'.format(vshunt,vshunt/res,vbus))

    if args.probe:
        bus.probe()
