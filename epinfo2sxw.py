#!/usr/bin/env python2

import nfs4st

def parse_method(meth):
    print "parsing method", meth.__name__

    # One row per method
    outfile.write('<table:table-row>\n')
    outfile.write('<table:table-cell table:style-name="Table2.A2" table:value-type="string">\n')
    outfile.write('<text:p text:style-name="Table Contents">%s</text:p>\n' % meth.__name__)
    outfile.write('</table:table-cell>\n')

    doc = meth.__doc__
    if doc:
        lines = doc.split("\n")
    else:
        lines = []

    while lines:
        line = lines[0]
        del lines[0]
        
        if line.find("Covered valid equivalence classes:") != -1:
            data = line[line.find(":") + 1:]
            data = data.strip()
            xmlstr = """
            <table:table-cell table:style-name="Table2.B3" table:value-type="string">
            <text:p text:style-name="P1">%s</text:p>
            </table:table-cell>
            """ 
            outfile.write(xmlstr % data)
            
        if line.find("Covered invalid equivalence classes:") != -1:
            data = line[line.find(":") + 1:]
            data = data.strip()
            xmlstr = """
            <table:table-cell table:style-name="Table2.A2" table:value-type="string">
            <text:p text:style-name="P1">%s</text:p>
            </table:table-cell>
            """
            outfile.write(xmlstr % data)

        if line.find("Comments:") != -1:
            data = line[line.find(":") + 1:]
            data = data.strip()
            # Use everything after comment
            for line in lines:
                data = data + " " + line.strip()
                del lines[0]

            xmlstr = """
            <table:table-cell table:style-name="Table2.D2" table:value-type="string">
            <text:p text:style-name="Table Contents">%s</text:p>
            </table:table-cell>
            """ 
            outfile.write(xmlstr % data)

            
    outfile.write('</table:table-row>\n')


def handle_valid_ec(lines):
    cell = ""
    while lines:
        line = lines[0]
        if line.find("            ") == -1:
            break
        del lines[0]
        if not cell:
            cell += line.strip()
        else:
            cell += ", " + line.strip()

    outfile.write('<table:table-cell table:style-name="Table1.A2" table:value-type="string">\n')
    outfile.write('<text:p text:style-name="Table Contents">%s</text:p>\n' % cell)
    outfile.write('</table:table-cell>\n')

def handle_invalid_ec(lines):
    cell = ""
    while lines:
        line = lines[0]
        if line.find("            ") == -1:
            break
        del lines[0]
        cell += line.strip()

    outfile.write('<table:table-cell table:style-name="Table1.C2" table:value-type="string">\n')
    outfile.write('<text:p text:style-name="Table Contents">%s</text:p>\n' % cell)
    outfile.write('</table:table-cell>\n')


def handle_ic(lines):
     while lines:
         line = lines[0]
         if line.find("        ") == -1:
             return
         
         del lines[0]
         if line.find("Valid equivalence classes:") != -1:
             print "Handling valid equivalence classes"
             handle_valid_ec(lines)

         if line.find("Invalid equivalence classes:") != -1:
             print "Handling invalid equivalence classes"
             handle_invalid_ec(lines)
         

def handle_ep(lines):

    while lines:
        line = lines[0]
        del lines[0]
        if line.find("Input Condition:") != -1:
            ic_name = line[line.find(":") + 2:]
            print "Handling Input Condition:", ic_name
            outfile.write("<table:table-row>\n")

            outfile.write('<table:table-cell table:style-name="Table1.A2" table:value-type="string">\n')
            outfile.write('<text:p text:style-name="Table Contents">%s</text:p>\n' % ic_name)
            outfile.write('</table:table-cell>\n')

            handle_ic(lines)
            outfile.write("</table:table-row>\n")


def class_output(klass):
    doc = klass.__doc__
    if not doc or doc.find("Equivalence partitioning:") == -1:
        print "Warning: %s has no Equivalence partitioning information" \
              % klass.__name__
        return
    lines = doc.split("\n")
    while lines:
        line = lines[0]
        del lines[0]
        if line.find("Equivalence partitioning:") != -1:
            handle_ep(lines)
            

def parse_testcase(klass):
    print "Parsing", klass.__name__
    eqhead = open("eqpart_head.xml").read()
    outfile.write(eqhead % klass.__name__)
    
    class_output(klass)

    outfile.write('</table:table>\n')
    outfile.write('<text:p text:style-name="Standard"><text:s/></text:p>\n')
    outfile.write('<text:p text:style-name="Standard"/>\n')

    tcpart_head = open("tcpart_head.xml").read()
    outfile.write(tcpart_head % klass.__name__)
    
    for methodname in dir(klass):
        if methodname.startswith("test"):
            method = eval("klass." + methodname)
            parse_method(method)
            
    outfile.write('</table:table>\n')

def main():
    global outfile
    outfile = open("testcases.xml", "w")
    headfile = open("testcases_head.xml")
    outfile.write(headfile.read())
    headfile.close()
    for attr in dir(nfs4st):
        if attr.endswith("TestCase"):
        #if attr == "AccessTestCase":
            parse_testcase(eval("nfs4st." + attr))

    ending = """
  <text:p text:style-name="Standard"/>
 </office:body>
</office:document-content>
"""
    outfile.write(ending)
    outfile.close()
    

if __name__ == '__main__':
    main()
