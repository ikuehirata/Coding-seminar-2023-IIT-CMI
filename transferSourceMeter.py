# -*- coding: utf-8 -*-
"""
measures transfer curves by
python transferSourceMeter.py Vg device# note
"""
from datetime import datetime as dt
import numpy as np
import os.path
import sys
import util
import visa
import plotmodule

vgstart = 0  # Vg start
vgstop = -20  # Vg stop
vgpoin = 51
vgstep = 1
vdstring = ""
TIMEOUT = 600e3  # timeout in milisecond
triggercount = 101

alldat = np.empty(1)
trigTranDelay = 0.2  # trigger transition delay
sourceWait = 0  # source wait
senseWait = 0.1  # sense wait
aper = 0.2  # measurement aperture time

desc = \
    """ This program is to measure transfer curves of a transistor.
Connections are below:
Ch 1 High Force Gate
Ch 1 Low Force Source/Ground
Ch 2 High Drain
Ch 2 Low Source/Ground
Probe 1: source = GND
Probe 2: drain = Ch2
Probe 3: gate = Ch1
"""


def setup_parameters():
    # show manual
    if sys.argv[1] == "h" or sys.argv[1] == "man":
        print(desc)
        raise Exception

    # input error
    if len(sys.argv) < 3:
        print("command example")
        print('python transfer.py maxVd deviceName (note for device)')
        raise Exception

    global vgstart, vgstop, vgstep, vgpoin, fname, vdlist, \
        vdstring, triggercount
    basefname = sys.argv[2]
    note = sys.argv[3] if len(sys.argv) > 3 else ""
    vgstop = float(sys.argv[1])

    # p-type starts from plus region
    vgstart = -1 * vgstop if vgstop < 0 else 0
    # vgstart = 0
    # vgstart = -1 * vgstop
    vgstep = (vgstop-vgstart)/(vgpoin-1)
    if vgstop > 0:
        vdlist = [vgstop/10 if vgstop/10 > 4 else 4, vgstop]
    else:
        vdlist = [vgstop/10 if vgstop/10 < -4 else -4, vgstop]
    vdstring = ",".join(map(str, np.repeat(vdlist, vgpoin*2)))
    triggercount = vgpoin*len(vdlist)*2

    if not os.path.exists('rawdata'):
        os.mkdir('rawdata')
    # check output file duplicate
    fname = util.checkSaveFileName(f"rawdata/slowTr{basefname}")
    # check with devNote
    util.checkdevNote(basefname, note)


def measurement():
    global alldat
    # open instrument
    rm = visa.ResourceManager("C:/Windows/System32/visa64.dll")
    pia = rm.open_resource('USB0::0x0957::0x8E18::MY51140120::0::INSTR')
    try:
        pia.timeout = TIMEOUT

        pia.write("*RST")
        pia.write(":sour1:func:mode volt")
        pia.write(":sour1:volt:mode swe")
        pia.write(f":sour1:volt:star {vgstart}")
        pia.write(f":sour1:volt:stop {vgstop}")
        pia.write(f":sour1:volt:poin {vgpoin}")
        pia.write(":SOUR1:SWE:STA DOUB")  # double sweep

        pia.write(":sour2:func:mode volt")
        pia.write(":sour2:volt:mode list")
        pia.write(f":sour2:list:volt {vdstring}")

        pia.write(":sens1:func \"curr\"")
        pia.write(":sens1:curr:prot 0.0001")
        pia.write(":sens2:curr:prot 0.0001")
        # sense wait time setup
        pia.write(":SENS1:WAIT:AUTO OFF")  # disables automatic sense wait time
        pia.write(":SENS2:WAIT:AUTO OFF")  # disables automatic sense wait time
        pia.write(f":sens1:curr:APER {aper}")  # aperture time
        pia.write(f":sens2:curr:APER {aper}")  # aperture time

        pia.write(":trig1:sour aint")
        pia.write(":trig2:sour aint")
        pia.write(f":trig1:coun {triggercount}")
        pia.write(f":trig2:coun {triggercount}")
        pia.write(f":TRIG1:TRAN:DEL {trigTranDelay:.1e}")
        pia.write(f":TRIG2:TRAN:DEL {trigTranDelay:.1e}")

        # display
        # pia.write(":disp:view grap")
        print(f"setup done {pia.query(':syst:err:all?')}", end=""),

        pia.write(":outp1 on")
        pia.write(":outp2 on")

        pia.write(":init (@1, 2)")
        pia.write("*WAI")
        igs = np.array(pia.query_ascii_values(":fetc:arr:curr? (@1)"))
        ids = np.array(pia.query_ascii_values(":fetc:arr:curr? (@2)"))
        vgs = np.array(pia.query_ascii_values(":fetc:arr:sour? (@1)"))
        vds = np.array(pia.query_ascii_values(":fetc:arr:sour? (@2)"))
        alldat = np.column_stack((vgs, ids, igs, vds))
        pia.write(":outp1 off")
        pia.write(":outp2 off")
    except Exception:
        pia.write(":abor")
        raise
    print(f"measurement done {pia.query(':syst:err:all?')}")
    return pia


def save(pia):
    # save data
    tab = "\t"
    head = f"""data file made from Agilent B2912A Precision \
Source/Measure Unit by transfer.py
URL: https://github.com/ikuehirata/Agilent_B2912A_Controller
Data file created at {dt.now().strftime('%Y-%m-%d %H:%M:%S')} UTC
Connection type {pia.query(':SENS:REM?')} (0 for 2-wire, 1 for 4-wire)
Trigger transition delay {trigTranDelay}
Trigger acquisition delay {pia.query(':TRIG:ACQ:DEL?').strip()}
Source wait time {sourceWait}
Sense wait time {senseWait}
Aperture time {aper}
Measurement.Primary.Start{tab}{vgstart}
Measurement.Primary.Stop{tab}{vgstop}
Measurement.Primary.Step{tab}{vgpoin}
Measurement.Secondary.Start{tab}{vdlist[0]}
Measurement.Secondary.Count{tab}{len(vdlist)}
Measurement.Secondary.Step{tab}{(vdlist[1]-vdlist[0])}
Vg{tab}Id{tab}Ig{tab}Vd"""
    np.savetxt(fname, alldat, delimiter='\t', header=head)

    # show plot
    plotmodule.plottransfer(fname, show=True)


def main():
    setup_parameters()
    pia = measurement()
    save(pia)


if __name__ == "__main__":
    main()
