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
    outfile.write(EQPART_HEAD % klass.__name__)
    
    class_output(klass)

    outfile.write('</table:table>\n')
    outfile.write('<text:p text:style-name="Standard"><text:s/></text:p>\n')
    outfile.write('<text:p text:style-name="Standard"/>\n')

    outfile.write(TCPART_HEAD % klass.__name__)
    
    for methodname in dir(klass):
        if methodname.startswith("test"):
            method = eval("klass." + methodname)
            parse_method(method)
            
    outfile.write('</table:table>\n')

def main():
    global outfile
    outfile = open("testcases.xml", "w")
    outfile.write(TESTCASES_HEAD)
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

#
# XML clips
#
EQPART_HEAD = """
  <table:table table:name="Table1" table:style-name="Table1">
   <table:table-column table:style-name="Table1.A" table:number-columns-repeated="3"/>
   <table:table-header-rows>
    <table:table-row>
     <table:table-cell table:style-name="Table1.A1" table:number-columns-spanned="3" table:value-type="string">
      <text:p text:style-name="Table Heading">Equivalence partitioning for %s</text:p>
     </table:table-cell>
     <table:covered-table-cell/>
     <table:covered-table-cell/>
    </table:table-row>
   </table:table-header-rows>
   <table:table-row>
    <table:table-cell table:style-name="Table1.A2" table:value-type="string">
     <text:p text:style-name="Table Heading">Input Conditions</text:p>
    </table:table-cell>
    <table:table-cell table:style-name="Table1.A2" table:value-type="string">
     <text:p text:style-name="Table Heading">Valid Equivalence Classes</text:p>
    </table:table-cell>
    <table:table-cell table:style-name="Table1.C2" table:value-type="string">
     <text:p text:style-name="Table Heading">Invalid Equivalence Classes</text:p>
    </table:table-cell>
   </table:table-row>
"""

TCPART_HEAD = """
  <table:table table:name="Table2" table:style-name="Table2">
   <table:table-column table:style-name="Table2.A"/>
   <table:table-column table:style-name="Table2.B"/>
   <table:table-column table:style-name="Table2.C"/>
   <table:table-column table:style-name="Table2.D"/>
   <table:table-header-rows>
    <table:table-row>
     <table:table-cell table:style-name="Table2.A1" table:number-columns-spanned="4" table:value-type="string">
      <text:p text:style-name="Table Heading">Test Cases for %s</text:p>
     </table:table-cell>
     <table:covered-table-cell/>
     <table:covered-table-cell/>
     <table:covered-table-cell/>
    </table:table-row>
   </table:table-header-rows>
   <table:table-row>
    <table:table-cell table:style-name="Table2.A2" table:value-type="string">
     <text:p text:style-name="Table Heading">Name</text:p>
    </table:table-cell>
    <table:table-cell table:style-name="Table2.A2" table:value-type="string">
     <text:p text:style-name="Table Heading">Covered valid equivalence classes</text:p>
    </table:table-cell>
    <table:table-cell table:style-name="Table2.A2" table:value-type="string">
     <text:p text:style-name="Table Heading">Covered invalid equivalence classes</text:p>
    </table:table-cell>
    <table:table-cell table:style-name="Table2.D2" table:value-type="string">
     <text:p text:style-name="Table Heading">Comments</text:p>
    </table:table-cell>
   </table:table-row>
"""

TESTCASES_HEAD = """\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE office:document-content PUBLIC "-//OpenOffice.org//DTD OfficeDocument 1.0//EN" "office.dtd">
<office:document-content xmlns:office="http://openoffice.org/2000/office" xmlns:style="http://openoffice.org/2000/style" xmlns:text="http://openoffice.org/2000/text" xmlns:table="http://openoffice.org/2000/table" xmlns:draw="http://openoffice.org/2000/drawing" xmlns:fo="http://www.w3.org/1999/XSL/Format" xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:number="http://openoffice.org/2000/datastyle" xmlns:svg="http://www.w3.org/2000/svg" xmlns:chart="http://openoffice.org/2000/chart" xmlns:dr3d="http://openoffice.org/2000/dr3d" xmlns:math="http://www.w3.org/1998/Math/MathML" xmlns:form="http://openoffice.org/2000/form" xmlns:script="http://openoffice.org/2000/script" office:class="text" office:version="1.0">
 <office:script/>
 <office:font-decls>
  <style:font-decl style:name="Arial Unicode MS" fo:font-family="&apos;Arial Unicode MS&apos;" style:font-pitch="variable"/>
  <style:font-decl style:name="HG Mincho Light J" fo:font-family="&apos;HG Mincho Light J&apos;" style:font-pitch="variable"/>
  <style:font-decl style:name="Thorndale" fo:font-family="Thorndale" style:font-family-generic="roman" style:font-pitch="variable"/>
 </office:font-decls>
 <office:automatic-styles>
  <style:style style:name="Table1" style:family="table">
   <style:properties style:width="16.999cm" table:align="margins"/>
  </style:style>
  <style:style style:name="Table1.A" style:family="table-column">
   <style:properties style:column-width="5.666cm" style:rel-column-width="21845*"/>
  </style:style>
  <style:style style:name="Table1.A1" style:family="table-cell">
   <style:properties fo:padding="0.097cm" fo:border="0.002cm solid #000000"/>
  </style:style>
  <style:style style:name="Table1.A2" style:family="table-cell">
   <style:properties fo:padding="0.097cm" fo:border-left="0.002cm solid #000000" fo:border-right="none" fo:border-top="none" fo:border-bottom="0.002cm solid #000000"/>
  </style:style>
  <style:style style:name="Table1.C2" style:family="table-cell">
   <style:properties fo:padding="0.097cm" fo:border-left="0.002cm solid #000000" fo:border-right="0.002cm solid #000000" fo:border-top="none" fo:border-bottom="0.002cm solid #000000"/>
  </style:style>


  <style:style style:name="Table2" style:family="table">
   <style:properties style:width="16.999cm" table:align="margins"/>
  </style:style>
  <style:style style:name="Table2.A" style:family="table-column">
   <style:properties style:column-width="4.03cm" style:rel-column-width="2285*"/>
  </style:style>
  <style:style style:name="Table2.B" style:family="table-column">
   <style:properties style:column-width="2.341cm" style:rel-column-width="1327*"/>
  </style:style>
  <style:style style:name="Table2.C" style:family="table-column">
   <style:properties style:column-width="2.431cm" style:rel-column-width="1378*"/>
  </style:style>
  <style:style style:name="Table2.D" style:family="table-column">
   <style:properties style:column-width="8.195cm" style:rel-column-width="4646*"/>
  </style:style>
  <style:style style:name="Table2.A1" style:family="table-cell">
   <style:properties fo:padding="0.097cm" fo:border="0.002cm solid #000000"/>
  </style:style>
  <style:style style:name="Table2.A2" style:family="table-cell">
   <style:properties fo:padding="0.097cm" fo:border-left="0.002cm solid #000000" fo:border-right="none" fo:border-top="none" fo:border-bottom="0.002cm solid #000000"/>
  </style:style>
  <style:style style:name="Table2.D2" style:family="table-cell">
   <style:properties fo:padding="0.097cm" fo:border-left="0.002cm solid #000000" fo:border-right="0.002cm solid #000000" fo:border-top="none" fo:border-bottom="0.002cm solid #000000"/>
  </style:style>
  <style:style style:name="Table2.B3" style:family="table-cell" style:data-style-name="N0">
   <style:properties fo:vertical-align="bottom" fo:padding="0.097cm" fo:border-left="0.002cm solid #000000" fo:border-right="none" fo:border-top="none" fo:border-bottom="0.002cm solid #000000"/>
  </style:style>
  <style:style style:name="Table2.B10" style:family="table-cell">
   <style:properties fo:vertical-align="top" fo:padding="0.097cm" fo:border-left="0.002cm solid #000000" fo:border-right="none" fo:border-top="none" fo:border-bottom="0.002cm solid #000000"/>
  </style:style>
  <style:style style:name="Table2.D10" style:family="table-cell" style:data-style-name="N0">
   <style:properties fo:vertical-align="bottom" fo:padding="0.097cm" fo:border-left="0.002cm solid #000000" fo:border-right="0.002cm solid #000000" fo:border-top="none" fo:border-bottom="0.002cm solid #000000"/>
  </style:style>
  <style:style style:name="P1" style:family="paragraph" style:parent-style-name="Table Contents">
   <style:properties fo:text-align="end" style:justify-single-word="false"/>
  </style:style>
  <number:number-style style:name="N0" style:family="data-style">
   <number:number number:min-integer-digits="1"/>
  </number:number-style>
 </office:automatic-styles>
 <office:body>
  <text:sequence-decls>
   <text:sequence-decl text:display-outline-level="0" text:name="Illustration"/>
   <text:sequence-decl text:display-outline-level="0" text:name="Table"/>
   <text:sequence-decl text:display-outline-level="0" text:name="Text"/>
   <text:sequence-decl text:display-outline-level="0" text:name="Drawing"/>
  </text:sequence-decls>
  <text:p text:style-name="Standard"/>
"""

    

if __name__ == '__main__':
    main()