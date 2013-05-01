#!/usr/bin/env python
#
# Fast Network Simulation Setup (FNSS), ns-2 adapter
#
# Copyright (c) 2013, Lorenzo Saino and Cosmin Cocora
# Contacts: http://fnss.github.com
# 
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
# MA 02110-1301, USA.
#
import argparse
import sys, re

try:
    from fnss.util import time_units, capacity_units
    from fnss.topologies.topology import read_topology
    from fnss.netconfig.nodeconfig import get_stack, \
                                          get_application_names, \
                                          get_application_properties
except ImportError:
    raise ImportError("The FNSS core package is needed to run this script. " \
                      "Install the FNSS core library and try again")


__all__ = ['convert_xml_to_ns2',
           'convert_object_to_ns2',
           'validate_ns2_stacks']

class __Templite(object):
    #
    # Templite+
    # A light-weight, fully functional, general purpose templating engine
    #
    # Copyright (c) 2009 joonis new media
    # Author: Thimo Kraemer <thimo.kraemer@joonis.de>
    #
    # Based on Templite by Tomer Filiba
    # http://code.activestate.com/recipes/496702/
    #
    # This program is free software; you can redistribute it and/or modify
    # it under the terms of the GNU General Public License as published by
    # the Free Software Foundation; either version 2 of the License, or
    # (at your option) any later version.
    #       
    # This program is distributed in the hope that it will be useful,
    # but WITHOUT ANY WARRANTY; without even the implied warranty of
    # MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    # GNU General Public License for more details.
    #       
    # You should have received a copy of the GNU General Public License
    # along with this program; if not, write to the Free Software
    # Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
    # MA 02110-1301, USA.
    #
    auto_emit = re.compile('(^[\'\"])|(^[a-zA-Z0-9_\[\]\'\"]+$)')
    
    def __init__(self, template, start='${', end='}$'):
        if len(start) != 2 or len(end) != 2:
            raise ValueError('each delimiter must be two characters long')
        delimiter = re.compile('%s(.*?)%s' % (re.escape(start), 
                                              re.escape(end)), re.DOTALL)
        offset = 0
        tokens = []
        for i, part in enumerate(delimiter.split(template)):
            part = part.replace('\\'.join(list(start)), start)
            part = part.replace('\\'.join(list(end)), end)
            if i % 2 == 0:
                if not part: continue
                part = part.replace('\\', '\\\\').replace('"', '\\"')
                part = '\t' * offset + 'emit("""%s""")' % part
            else:
                part = part.rstrip()
                if not part: continue
                if part.lstrip().startswith(':'):
                    if not offset:
                        raise SyntaxError(
                            'no block statement to terminate: ${%s}$' % part)
                    offset -= 1
                    part = part.lstrip()[1:]
                    if not part.endswith(':'): continue
                elif self.auto_emit.match(part.lstrip()):
                    part = 'emit(%s)' % part.lstrip()
                lines = part.splitlines()
                margin = min(len(l) - len(l.lstrip()) 
                             for l in lines if l.strip())
                part = '\n'.join('\t' * offset + l[margin:] for l in lines)
                if part.endswith(':'):
                    offset += 1
            tokens.append(part)
        if offset:
            raise SyntaxError('%i block statement(s) not terminated' % offset)
        self.__code = compile('\n'.join(tokens), 
                              '<templite %r>' % template[:20], 'exec')

    def render(self, __namespace=None, **kw):
        """
        Render the template according to the given namespace
        
        Parameters
        ---------- 
        __namespace :dict
            A dictionary serving as a namespace for evaluation
        **kw : keyword arguments
            Keyword arguments which are added to the namespace
        """
        namespace = {}
        if __namespace: namespace.update(__namespace)
        if kw: namespace.update(kw)
        namespace['emit'] = self.write
        
        __stdout = sys.stdout
        sys.stdout = self
        self.__output = []
        eval(self.__code, namespace)
        sys.stdout = __stdout
        return ''.join(self.__output)
    
    def write(self, *args):
        for a in args:
            self.__output.append(str(a))



# Template text rendered by the template engine
__template = r"""# Code generated by Fast Network Simulator Setup (FNSS)
@{
from fnss.util import time_units, capacity_units
from fnss.netconfig.nodeconfig import get_stack, \
                                      get_application_names, \
                                      get_application_properties

# Convert capacity in Mb
capacity_norm = capacity_units[topology.graph['capacity_unit']] / 1000000.0

# Convert delay it in ms
if set_delays: delay_norm = time_units[topology.graph['delay_unit']]
}@
#Create a simulator object
set ns [new Simulator]

#Create nodes
@{
for node in topology.nodes_iter():
    emit("set n%s [$ns node]\n" % str(node))
}@
# Create all links
set qtype DropTail
@{
# if topology is undirected, create duplex links, otherwise simplex links
if topology.is_directed():
    for u, v in topology.edges_iter():
        delay = "0" if not set_delays else str(topology.edge[u][v]['delay'] * delay_norm)
        emit("$ns simplex-link $n%s $n%s %sMb %sms $qtype\n"
             % (str(u), str(v), str(topology.edge[u][v]['capacity'] * capacity_norm),
                delay))
else:
    for u, v in topology.edges_iter():
        delay = "0" if not set_delays else str(topology.edge[u][v]['delay'] * delay_norm)
        emit("$ns duplex-link $n%s $n%s %sMb %sms $qtype\n"
             % (str(u), str(v), str(topology.edge[u][v]['capacity'] * capacity_norm),
                delay))

if set_weights:
    emit("\n# Set link weights\n")
    for u, v in topology.edges_iter():
        emit("$ns cost $n%s $n%s %s\n" 
             % (str(u), str(v), str(topology.edge[u][v]['weight'])))
        if not topology.is_directed():
            emit("$ns cost $n%s $n%s %s\n" 
                 % (str(v), str(u), str(topology.edge[v][u]['weight'])))

if set_buffers:
    emit("\n# Set queue sizes\n")
    for u, v in topology.edges_iter():
        emit("$ns queue-limit $n%s $n%s %s\n" 
             % (str(u), str(v), str(topology.edge[u][v]['buffer'])))
        if not topology.is_directed():
            emit("$ns queue-limit $n%s $n%s %s\n" 
                 % (str(v), str(u), str(topology.edge[v][u]['buffer'])))

if deploy_stacks:
    emit("\n# Deploy applications and agents\n")
    for node in topology.nodes_iter():
        stack = get_stack(topology, node)
        if stack is None: continue
        stack_name, stack_props = stack
        stack_class = stack_props['class']
        emit("set %s [new %s]\n" % (str(stack_name), str(stack_class)))
        for prop_name, prop_val in stack_props.items():
            if prop_name == 'class': continue
            emit("$%s set %s %s\n"
                 % (str(stack_name), str(prop_name), str(prop_val)))
        emit("$ns attach-agent $n%s $%s\n\n" % (str(node), str(stack_name)))
        
        for app_name in get_application_names(topology, node):
            app_properties = get_application_properties(topology, 
                                                        node,
                                                        app_name)
            app_class = app_properties['class']
            emit("set %s [new %s]\n" % (str(app_name), str(app_class)))
            for prop_name, prop_val in app_properties.items():
                if prop_name == 'class':  continue
                emit("$%s set %s %s\n" 
                     % (str(app_name), str(prop_name), str(prop_val)))
            emit("$%s attach-agent $%s\n" % (str(app_name), str(stack_name)))
}@
"""


def __print_log(level, message):
    green = '\033[92m'
    yellow = '\033[93m'
    red = '\033[91m'
    end = '\033[0m'
    if level is 'error':
        message = "".join([red, '[ERROR] ', message, end])
    elif level is 'warning':
        message = "".join([yellow, '[WARNING] ', message, end])
    elif level is 'info':
        message = "".join([green, '[INFO] ', message, end])
    print(message)


def validate_ns2_stacks(topology):
    """
    Validate whether the stacks and applications of a topology are valid for
    ns-2 deployment
    
    Parameters
    ----------
    topology : Topology
        The topology object to validate
    """
    for node in topology.nodes_iter():
        applications = get_application_names(topology, node)
        for name in applications:
            if not 'class' in get_application_properties(topology, node, name):
                # Each application must have a class attribute to work
                return False
        stack = get_stack(topology, node)
        if stack is None:
            # Each node must have a stack if it has an application
            if len(applications) > 0: return False 
        else:
            # If there is a stack, it must have a class attribute
             if 'class' not in stack[1]: return False
    return True
            

def convert_objects_to_ns2(topology, ns2_file, deploy_stacks=True, log=False):
    """
    Converts topology and schedule objects into an ns-2 Tcl script
    
    Parameters
    ----------
    topology : Topology
        The Topology object to convert
    ns2_file : str
        The path of the output Tcl file
    deploy_stacks : bool, optional
        If True, read the stacks on nodes and write them into the output file.
        For this to work, stacks must be formatted in a way understandable by
        ns-2. For example, stack and applications must have a 'class' attribute
        whose value is the name of the ns-2 class implementing it.
    log : bool, optional
        If True, print log info on screen and does not raise Error in case
        something goes wrong. If False does not print logs but raises errors
        when something goes wrong.
    """
    set_buffers = True
    set_delays = True
    
    # if all links are annotated with weights, then set weights
    set_weights = all('weight' in topology.edge[u][v]
                      for u, v in topology.edges_iter())
    
    if not 'capacity_unit' in topology.graph:
        if log: 
            __print_log('error', 
                        'Missing capacity unit attribute in the topology. '\
                        'Set capacities and try again.')
            return
        else:
            raise ValueError('The given topology does not have capacity data.')
    if not topology.graph['capacity_unit'] in capacity_units:
        if log: 
            __print_log('error', 
                        'The capacity unit attribute of the topology (%s) '\
                        'cannot be recognized.'
                        % topology.graph['capacity_unit'])
            return
        else:
            raise ValueError('The given topology does not have a valid capacity unit')
    if not 'buffer_unit' in topology.graph:
        if log: __print_log('warning', 
                            'Missing buffer size unit attribute in the topology. '\
                            'Output file will be generated without buffer assignments.')
        set_buffers = False
    elif not topology.graph['buffer_unit'] == 'packets':
        if log: __print_log('warning', 
                            'The buffer size unit of the topology is %s. '\
                            'The only supported unit is packets. Output file will be '\
                            'generated without buffer assignments'
                            % topology.graph['buffer_unit'])
        set_buffers = False
    if not 'delay_unit' in topology.graph or not topology.graph['delay_unit'] in time_units:
        if log: __print_log('warning', 
                            'Missing or invalid delay unit attribute in the topology. '\
                            'Output file will be generated with all link delays set to 0.')
        set_delays = False
    if deploy_stacks:
        if not validate_ns2_stacks(topology):
            if log: __print_log('warning', 'Some application stacks cannot be parsed correctly. '\
                                'Read the documentation to learn how to properly configure stacks. ' \
                                'Output file will be generated without stack assignments.')
            deploy_stacks = False
        if not any('stack' in topology.node[v] for v in topology.nodes_iter()):
            deploy_stacks = False
    template = __Templite(__template, start='@{', end='}@')
    out_file = open(ns2_file, "w")
    out_file.write(template.render({'topology':      topology,
                                    'deploy_stacks': deploy_stacks,
                                    'set_delays':    set_delays,
                                    'set_buffers':   set_buffers,
                                    'set_weights':   set_weights},
                                 x=8))
    out_file.close()
    if log: __print_log('info', 'Output file created successfully')


def convert_xml_to_ns2(topology_file, ns2_file, deploy_stacks=True, log=False):
    """
    Convert topology and schedule XML files into an ns-2 Tcl script
    
    Parameters
    ----------
    topology_file : str
        The path of the input topology XML file
    ns2_file : str
        The path of the output Tcl file
    deploy_stacks : bool, optional
        If True, read the stacks on nodes and write them into the output file.
        For this to work, stacks must be formatted in a way understandable by
        ns-2. For example, stack and applications must have a 'class' attribute
        whose value is the name of the ns-2 class implementing it.
    log : bool, optional
        If True, print log info on screen and does not raise Error in case
        something goes wrong. If False does not print logs but raises errors
        when something goes wrong.
    """
    topology = read_topology(topology_file)
    convert_objects_to_ns2(topology, ns2_file, deploy_stacks, log)


def main():
    """Parse topology file and convert it to an ns-2 Tcl script"""
    parser = argparse.ArgumentParser()
    parser.add_argument("-t", "--topology",
                        help='The topology XML file',
                        required=True)
    parser.add_argument("ns2file",
                        help="The file where the ns-2 Tcl script is written")
    args = parser.parse_args()
    convert_xml_to_ns2(args.topology, args.ns2file, 
                       deploy_stacks=True, log=True)

if __name__ == '__main__':
    main()