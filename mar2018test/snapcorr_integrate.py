#!/usr/bin/env python

import time,struct,sys,logging,numpy as np,argparse
import matplotlib.pyplot as plt, matplotlib.ticker as ticker
from casperfpga import CasperFpga
from casperfpga import adc,bitsnap,snapadc

def get_auto_data(fpga, baseline, nch=1024):

    fmt = '>{}I'.format(nch/2)

    data = np.zeros((nch))
    data[0::2] = struct.unpack(fmt,fpga.read('dir_x0_{}_real'.format(baseline),nch*2))
    data[1::2] = struct.unpack(fmt,fpga.read('dir_x1_{}_real'.format(baseline),nch*2))

    return data

#START OF MAIN:

if __name__ == '__main__':

    p = argparse.ArgumentParser(description='Plot SNAP outputs.',
        epilog='E.g.\npython snapcorr_plot.py 10.1.0.23',
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('snap', type=str, metavar="SNAP_IP_OR_HOSTNAME")
    p.add_argument('-n', '--nchannel', dest='nch',type=int, default=1024,
        help='The number of frequency channel. Default is 1024.')
    p.add_argument('--soft', type=int, default=1,
        help='Software integration length')
    p.add_argument('--hard', type=int,
        help='Hardware integration length, E.g. 244140')
    p.add_argument('--linear', action='store_true', default=False,
        help='Plot curve linearly')
    p.add_argument('-p', '--plot', nargs='?', type=str, default=None, const='display',
        help='Plot figure')
    p.add_argument('--dump', nargs='?', type=str, default=None, const='spectrum.txt',
        help='Save data to file')
    args = p.parse_args()

    print('Connecting to server {0}... '.format(args.snap)),
    fpga=CasperFpga(args.snap)
    time.sleep(1)

    if fpga.is_running():
        print 'ok\n'
    else:
        print 'ERROR connecting to server {0}.'.format(snap)
        sys.exit()

    if args.hard:
        print('Configuring accumulation period with {}.'.format(args.hard))
        fpga.write_int('acc_len',args.hard)

    clk = fpga.estimate_fpga_clock()
    acc_len = fpga.read_uint('acc_len')
    acc_len_in_sec = round(acc_len * (args.nch/2) / clk / 1e6, 2)
    print('Hardware integration length: {} seconds.'.format(acc_len_in_sec))
    acc_num_prev = fpga.read_uint('acc_num')
    acc_num_curr = acc_num_prev

    xaxis = np.arange(0, clk*4/2, clk*4/2 / args.nch)

    da = np.zeros_like(get_auto_data(fpga, 'aa' ,args.nch))
    db = np.zeros_like(da)
    dc = np.zeros_like(da)

    # print auto-correlation
    print('Collecting auto-correlation data...')
    for i in range(args.soft):
        while acc_num_curr == acc_num_prev:
            time.sleep(acc_len_in_sec / 2)
            acc_num_curr = fpga.read_uint('acc_num')
        acc_num_prev = acc_num_curr
        print('Integration #{}'.format(i))
        da += get_auto_data(fpga, 'aa' ,args.nch)
        db += get_auto_data(fpga, 'bb' ,args.nch)
        dc += get_auto_data(fpga, 'cc' ,args.nch)

    if args.dump:
        data_to_file = np.asarray([xaxis,da,db,dc]).T
        np.savetxt(args.dump, data_to_file)

    print('Ploting auto-correlation...')

    da[da==0] = 1
    db[db==0] = 1
    dc[dc==0] = 1
    label = ['aa','bb','cc']
    fig, ax = plt.subplots()
    if args.linear:
        ax.plot(xaxis,da,label='aa')
        ax.plot(xaxis,db,label='bb')
        ax.plot(xaxis,dc,label='cc')
        ax.set_ylabel('auto-correlation in linear mode')
    else:
        ax.plot(xaxis,10*np.log10(da),label='aa')
        ax.plot(xaxis,10*np.log10(db),label='bb')
        ax.plot(xaxis,10*np.log10(dc),label='cc')
        ax.set_ylabel('auto-correlation' + 'in relative dBm')
    
    sw_acc_len_in_sec = round(acc_len_in_sec * args.soft, 2)

    ax.set_xlabel('Frequency in MHz')
    ax.set_title('hw int {}s, total int {}s.'.format(acc_len_in_sec, sw_acc_len_in_sec))
    ax.legend(loc=0)
    plt.autoscale(enable=True,axis='both')

    if args.plot:
        if args.plot=='display':
            plt.show()
        else:
            plt.savefig(args.plot, dpi=300)

