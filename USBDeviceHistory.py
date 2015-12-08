# USBDeviceHistory.py
# Eric Odpyke
#
#
# ERIC OPDYKE licenses this file to you under the Apache License, Version
# 2.0 (the "License"); you may not use this file except in compliance with the
# License.  You may obtain a copy of the License at:
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.  See the License for the specific language governing
# permissions and limitations under the License.
#
# Discovers USB device history on Windows 7,8 for a user, given specific files.



from datetime import datetime
import subprocess
import argparse
import _winreg
import sys
import os


def load(args):
    #using windows reg command, mount the supplied registry hives
    devnull = open(os.devnull, 'w')
    try:
        subprocess.call("reg LOAD HKU\DRIVE_INFO_1 "+'"'+args.sys+'"', stdout = devnull)
        subprocess.call("reg LOAD HKU\DRIVE_INFO_2 "+'"'+args.software+'"', stdout = devnull)
        subprocess.call("reg LOAD HKU\DRIVE_INFO_3 "+'"'+args.ntuser+'"', stdout = devnull)
    except IndexError:
        sys.exit('\nPlease supply the path to the SYSTEM,SOFTWARE,NTUSER files in that order!')
    return args

        
def enum(key, supplied_key):
    value_name_data = {}
    control_key = key+supplied_key
    handle = _winreg.OpenKey(_winreg.HKEY_USERS, control_key)
    for i in xrange(0, _winreg.QueryInfoKey(handle)[1]):
        name, data, type = _winreg.EnumValue(handle, i)
        try:
            data_worked = data[::2][:data[::2].find(b'\x00')].decode()
            value_name_data[name]=data_worked
        except UnicodeDecodeError:         
            value_name_data[name]= data[::2]
    return value_name_data

  
def get_currentcontrolset(control_key):
    handle = _winreg.OpenKey(_winreg.HKEY_USERS, control_key)
    for i in xrange(0, _winreg.QueryInfoKey(handle)[1]):
        name, data, type = _winreg.EnumValue(handle, i)
        if name == "Current":
            return data
        else:
            pass


def enum_all(key, supplied_key):
    #This function is used to dig into registry keys that have 1 or more sub keys
    sub_key_list =[]
    control_key = key+supplied_key
    try:
        handle = _winreg.OpenKey(_winreg.HKEY_USERS, control_key)
        try:
            sub_keys, values, time = _winreg.QueryInfoKey(handle)
            for i in xrange(sub_keys):
                subkey = _winreg.EnumKey(handle, i)
                sub_key_list.append(subkey)
        except WindowsError:
            pass
    except WindowsError:
        print '[X] Arguments must be supplied in order!'
        print '\t[-] Argument order: SYSTEM SOFTWARE NTUSER SetupApi.dev.log'
        unload()
        sys.exit()
    return sub_key_list



def sort_subkeys(key, subkeys):
    #returns dictionary of devices and s/n
    usb_serial_numer ={}
    for sub_key in subkeys:
            extension_key = key+'\\'+sub_key
            handle = _winreg.OpenKey(_winreg.HKEY_USERS, extension_key)
            keys, values, time = _winreg.QueryInfoKey(handle)
            holding = []
            for i in xrange(keys):
                subkey = _winreg.EnumKey(handle, i)
                holding.append(subkey)
            usb_serial_numer[sub_key] = holding
            
    return usb_serial_numer


            
def get_friendly_name(key, wpd):
    usb_info = {}
    for device in wpd:
        serial_key = key+'\\'+device
        handle = _winreg.OpenKey(_winreg.HKEY_USERS, serial_key)
        holding = []
        for i in xrange(0, _winreg.QueryInfoKey(handle)[1]):
            name, data, type = _winreg.EnumValue(handle, i)
            if name == 'FriendlyName':
                holding.append(data)    
            else:
                pass
        usb_info[device] = holding
    return usb_info
                

def get_guid(mounted_devices, sort_wpd):
    #match volume guid to device and friendly name to be searched across an NTUSER
    usb_info = {}
    devices = []
    guids = []
    for key, value in sort_wpd.iteritems():
        key = key.split('_USBSTOR#').pop(-1).lower().split('{').pop(0)
        devices.append(key)
    for k, v in mounted_devices.iteritems():
        v = v.split('_USBSTOR#').pop(-1).lower().split('{').pop(0)
        guids.append(v)
    for device in devices:
        if device in guids:
            guid_id = guids.index(device)
            guid_to_use = guids[guid_id]
            for key, value in sort_wpd.iteritems():
                serial = device.split('#').pop(-2)
                if serial in key.lower():
                    friendly = value
                for k,v in mounted_devices.iteritems():
                    try:
                        if guid_to_use in v.lower():
                            volume = k
                            usb_info[volume]=[device, friendly]
                    except:
                        pass

               #guid:device,friendly
    return usb_info


def compare_mount_points2_usb(usb_info, mount_points):
        usb = {}
        for point in mount_points:
            for volume, data in usb_info.iteritems():
                if point in volume:
                    usb[point]=data
        if len(usb) == 0:
            print '\n[X] No USB device history found!'
        
        return usb


def setupapi(f, usb_stuff):
    serials =[]
    usb_with_time ={}
    for guid, data in usb_stuff.iteritems():
        for device in data:
            try:
                serial = device.split('#').pop(-2)
                try:
                    setup_file = open(f, 'r')
                except IOError:
                    print '\n[X] No such file ' + f
                    return 'flag'
                for line in setup_file:
                    if serial in line.lower():
                        first_time = (next(setup_file).split('start').pop(-1).strip('\n').split('.').pop(0))
                        usb_stuff[guid] = [data,first_time]
            except AttributeError:
                pass

    return usb_stuff


def master_dictionary(usb):
    master_usb_dictionary = {}
    for guid, info in usb.iteritems():
        for info_bit in info:
            if isinstance(info_bit, list):
                ident = info_bit[0]
                serial = ident.split('#').pop(-2)
                friendly = info_bit[1]
                master_usb_dictionary[guid]=[ident, serial, friendly]
            else:
                install = info_bit
                master_usb_dictionary[guid].append(install)
    return master_usb_dictionary


def last_connection_time(ntuser_key, master_usb_dictionary):
    for guid, info in master_usb_dictionary.iteritems():
        given_key = ntuser_key+r'\Software\Microsoft\Windows\CurrentVersion\Explorer\MountPoints2'+'\\'+guid
        handle =_winreg.OpenKey(_winreg.HKEY_USERS, given_key)
        last_connection_time = _winreg.QueryInfoKey(handle)[2]
        time = str(datetime.utcfromtimestamp(float(last_connection_time)*1e-7 - 11644473600)).split('.').pop(0)
        master_usb_dictionary[guid].append(time)
    return master_usb_dictionary


def get_vendor_prod_ver(info):
    new_list = info.split('&')
    for x in new_list:
        if x.startswith('ven_'):
            vendor = x.split('ven_').pop(-1)
        elif x.startswith('prod_'):
            product = x.split('prod_').pop(-1)
        elif x.startswith('rev_'):
            version = x.split('rev_').pop(-1).split('#').pop(0)
    if len(vendor) == 0:
        vendor = 'UNKNOWN'
    if len(product) == 0:
        product = 'UNKNOWN'
    if len(version) == 0:
        version = 'UNKNOWN'
    return vendor,product,version
    

def to_screen(master):
    for guid, info in master.iteritems():
        print '\nVolume Guid: ' + guid
        vendor,product,version = get_vendor_prod_ver(info[0])
        print 'Vendor: '+vendor
        print 'Product: '+product
        print 'Version: '+version
        print 'Unique Serial: '+info[1]
        print 'Friendly Name: '+info[2][0]
        print 'First Connection: '+ info[3]
        print 'Last Connection: '+ info[4].replace('-','/')+'\n'
        

def unload():
    devnull = open(os.devnull, 'w')
    subprocess.call("reg UNLOAD HKU\DRIVE_INFO_1", stdout = devnull)
    subprocess.call("reg UNLOAD HKU\DRIVE_INFO_2", stdout = devnull)
    subprocess.call("reg UNLOAD HKU\DRIVE_INFO_3", stdout = devnull)
    return


    

def write_to_file(location, master_usb_history):
    try:
        with open(location, 'a') as f:
            for guid, info in master_usb_history.iteritems():
                f.write('\nVolume Guid: ' + guid)
                vendor,product,version = get_vendor_prod_ver(info[0])
                f.write('\nVendor: '+vendor)
                f.write('\nProduct: '+product)
                f.write('\nVersion: '+version)
                f.write('\nUnique Serial: '+info[1])
                f.write('\nFriendly Name: '+info[2][0])
                f.write('\nFirst Connection: '+ info[3])
                f.write('\nLast Connection: '+ info[4].replace('-','/')+'\n')
            f.close()
    except IOError:
        print '[X] '+location+ ' not found'
        unload()
        sys.exit()

if __name__ == '__main__':

    #Argument parser to standaridize the order of arguments.
    parser = argparse.ArgumentParser(description='Discover the USB device history for a specified user.')
    parser.add_argument('sys', type=str, help='Path to the evidence system hive.')
    parser.add_argument('software', type=str, help='Path to the evidence software hive.')
    parser.add_argument('ntuser.dat', type=str, help='Path to the user\'s ntuser.dat')
    parser.add_argument('setupapi.dev.log', type=str, help='Path to the evidence setupapi.dev.log')
    parser.add_argument('-O', '--outfile',type=str, help='Path to output file.')
    args = parser.parse_args()                  

    #using window reg command, mount the registry hives.
    load(args)

    #establishing the registry hive names for use
    sys_key = r'DRIVE_INFO_1'
    soft_key = r'DRIVE_INFO_2'
    ntuser_key = r'DRIVE_INFO_3'
     
    try:
        #discover the current control set as specfied in the registry.
        control_key = sys_key+r'\Select'
        currentcontrolset = get_currentcontrolset(control_key)
        key = sys_key+r'\ControlSet00'+str(currentcontrolset)
    except:
        key = sys_key+r'\ControlSet001\Control'

    #returns a list of all the usb devices    
    usbstor_subkeys = enum_all(key, r'\Enum\USBSTOR')
    
    #returns a dictionary of all the serials numbers for ech usb device
    sort_usbstor = sort_subkeys(key+r'\Enum\USBSTOR', usbstor_subkeys)

    #returns a list of all the vendor Id,Product ID keys, I'll call usb keys
    enum_usb = enum_all(key, r'\Enum\USB')

    #returns a dictionary of usb keys and the keys serials
    sort_enum_usb = sort_subkeys(key+r'\Enum\USB', enum_usb)

    #returns a list of devices entries under the window portable devices key
    wpd = enum_all(soft_key, r'\Microsoft\Windows Portable Devices\Devices')

    #returns a dictionary of the device entries and the friendly names or drive letters associated
    sort_wpd= get_friendly_name(soft_key+r'\Microsoft\Windows Portable Devices\Devices', wpd)

    #returns a dictionary of the mounted devices and the volume guid
    mounted_devices = enum(sys_key, r'\MountedDevices')
    
    #from the supplied ntuser.dat, retrun a list of all volume guids for this user
    mountpoints2 = enum_all(ntuser_key, r'\Software\Microsoft\Windows\CurrentVersion\Explorer\MountPoints2')

    #cross reference the dictionaries to determine the volume guid:device ID and friendly name
    usb_info = get_guid(mounted_devices, sort_wpd)

    #cross reference the dictionaries to determine if the user has any usb history
    usb_history = compare_mount_points2_usb(usb_info, mountpoints2)

    #Read in the setupapi.dev.log file, search for the unique serial and discover the first connection time
    usb_with_time = setupapi(args.setupapi, usb_history)

    #handle to the file not being supplied.  This can likely be removed, this check is handled by argparser.
    if usb_with_time == 'flag':
        unload()
        sys.exit()

    #Build the master usb device history dictionary with all values described above.
    hold_usb_dictionary = master_dictionary(usb_with_time)

    #Using the supplied ntuser.dat file, parse the registry key attributes determing the last connection time
    master_usb_history= last_connection_time(ntuser_key, hold_usb_dictionary)

    if args.outfile:
        write_to_file(args.outfile, master_usb_history)
    else:
        #Parse the dictionary and format output for printing in the terminal
        to_screen(master_usb_history)

    #using the reg command unload the supplied registry hives.
    unload()
