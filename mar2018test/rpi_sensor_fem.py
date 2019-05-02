#!/usr/bin/env python

from __future__ import print_function
from casperfpga import i2c_volt,i2c_bar,i2c_eeprom,i2c_motion,i2c_sn,i2c_temp,i2c_gpio,i2c
import numpy as np,time,logging,struct,random,sys,argparse

logger = logging.getLogger(__name__)

def number(s):
    if s.startswith('0b'):
        val=int(s,2)
    elif s.startswith('0x'):
        val=int(s,16)
    else:
        val=int(s)
    return val

if __name__ == "__main__":

    p = argparse.ArgumentParser(description='Test FEM module. Use this script when RPI directly connects to Full Control Breakout board for HERA. Before trying this script, please install pigpio and run sudo pigpiod.',
epilog="""Examples:
python rpi_sensor_fem.py --i2c 1 10000 --gpio
python rpi_sensor_fem.py --i2c 1 10000 --gpio 0xff
python rpi_sensor_fem.py --i2c 1 10000 --rom
python rpi_sensor_fem.py --i2c 1 10000 --rom 'Hello world!'
python rpi_sensor_fem.py --i2c 1 10000 --volt
python rpi_sensor_fem.py --i2c 1 10000 --temp
python rpi_sensor_fem.py --i2c 1 10000 --bar
python rpi_sensor_fem.py --i2c 1 10000 --imu
python rpi_sensor_fem.py --i2c 1 10000 --switch
python rpi_sensor_fem.py --i2c 1 10000 --switch noise""",
formatter_class=argparse.RawDescriptionHelpFormatter)

    p.add_argument('--i2c', dest='i2c', type=int, metavar=('I2C_NAME'), choices=[1,2,3], required=True,
                help='Specify the name the i2c bus.')
    p.add_argument('--baud', dest='baud', type=int, metavar=('I2C_BAUD_RATE'), default=10000,
                help='Specify the baud rate of the i2c bus.')
    p.add_argument('--rom', nargs='?', metavar=('TEXT'), const='', help='Test EEPROM. Leave parameter empty to read ROM. Add text to write ROM.')
    p.add_argument('--temp', action='store_true', default=False, help='Print temperature.')
    p.add_argument('--sn', action='store_true', default=False, help='Print ID inside temperature sensor')
    p.add_argument('--volt', action='store_true', default=False, help='Print shunt voltage, shunt current and bus voltage.')
    p.add_argument('--bar', action='store_true', default=False, help='Print air pressure, temperature and height and calibrated height.')
    p.add_argument('--imu', action='store_true', default=False, help='Print FEM pose, that is theta and phi value')
    p.add_argument('--probe', action='store_true', default=False, help='Detect devices on the bus')
    g=p.add_mutually_exclusive_group()
    g.add_argument('--gpio', nargs='?', const=-1, type=number, metavar=('VALUE'), help='Test GPIO. Leave parameter empty to read gpio. Add value to write gpio.')
    g.add_argument('--switch',nargs='?', type=str, const='', metavar=('MODE'), choices=['', 'antenna','noise','load'], help='Switch FEM input to antenna, noise source or 50 ohm load. Choices are load, antenna, and noise.')
    args = p.parse_args()

    #      0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f
    # 00:          -- -- -- -- -- -- -- -- -- 0c -- -- --
    # 10: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
    # 20: 20 21 -- -- -- -- -- -- -- -- -- -- -- -- -- --
    # 30: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
    # 40: 40 -- -- -- -- -- -- -- -- -- -- -- -- -- -- 4f
    # 50: 50 51/52 -- -- -- -- -- -- -- -- -- -- -- -- --
    # 60: -- -- -- -- -- -- -- -- -- 69 -- -- -- -- -- --
    # 70: -- -- -- -- -- -- -- 77

    ACCEL_ADDR = 0X69   #
    MAG_ADDR = 0x0c     #
    BAR_ADDR = 0x77     #
    VOLT_FEM_ADDR = 0x4e    #
    VOLT_PAM_ADDR = 0x4f
    ROM_FEM_ADDR = 0x51 #
    ROM_PAM_ADDR = 0x52
    TEMP_ADDR = 0x40    #
    INA_ADDR = 0x45    #
    SN_ADDR = 0x50
    GPIO_PAM_ADDR = 0x21
    GPIO_FEM_ADDR = 0x20    #

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

    if args.imu:
        imu = i2c_motion.IMUSimple(bus,ACCEL_ADDR,orient=[[0,0,1],[1,1,0],[-1,1,0]])
        imu.init()
        theta, phi = imu.pose
        print('{}, {}'.format(theta,phi))
        imu.mpu.powerOff()

    if args.temp:
        temp = i2c_temp.Si7051(bus,TEMP_ADDR)
        t = temp.readTemp()
        print(t)

    if args.sn:
        temp = i2c_temp.Si7051(bus,TEMP_ADDR)
        sn=temp.sn()
        print(sn)

    if args.switch!=None:
        gpio=i2c_gpio.PCF8574(bus,GPIO_FEM_ADDR)
        if args.switch=='':
            smode = {0b000:'load',0b111:'antenna', 0b001:'noise'}
            val=gpio.read()
            if val in smode:
                print(smode[val])
            else:
                print('Unknown')
        else:
            smode = {'load':0b000,'antenna':0b111,'noise':0b001}
            gpio.write(smode[args.switch])
    elif args.gpio!=None:
        gpio=i2c_gpio.PCF8574(bus,GPIO_FEM_ADDR)
        if args.gpio<0:
            val=gpio.read()
            print('0b{:08b}'.format(val))
        else:
            gpio.write(args.gpio)

    if args.rom!=None:
        rom=i2c_eeprom.EEP24XX64(bus,ROM_FEM_ADDR)
        if args.rom=='':
            print(rom.readString())
        else:
            rom.writeString(args.rom)

    if args.bar:
        bar = i2c_bar.MS5611_01B(bus,BAR_ADDR)
        bar.init()
        rawt,dt = bar.readTemp(raw=True)
        press = bar.readPress(rawt,dt)
        alt = bar.toAltitude(press,rawt/100.)
        print('{},{},{},{}'.format(rawt/100.,press,alt,alt-0.16))

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
