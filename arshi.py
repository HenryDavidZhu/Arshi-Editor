import tkinter as tk
import tkinter.filedialog
import traceback
import tkinter.ttk as ttk
import tkinter.font

from tkinter import messagebox
from tkinter import colorchooser

from pygments import lex
from pygments.lexers import PythonLexer

import sys

import os

import re

import time

import difflib

import threading

import traceback

import webbrowser

import autopep8

wraptype = "char"

try:
    with open("resources/wraptype.txt") as file:
        wraptype = file.read().strip()
except:
    pass

tabSpace = 4

try:
    with open("resources/tabspace.txt") as file:
        tabSpace = int(str(file.read().strip()))
except:
    pass

openFiles = []
selectedFiles = 0

themeColors = []

try:
    with open("themes/theme.txt") as file:
        themeColors = file.read().split("\n")
except:
    pass

class TextLineNumbers(tk.Canvas):

    def __init__(self, *args, **kwargs):
        tk.Canvas.__init__(self, *args, **kwargs)
        self.textwidget = None

    def attach(self, text_widget):
        self.textwidget = text_widget

    def redraw(self, *args):
        '''redraw line numbers'''
        self.delete("all")

        i = self.textwidget.index("@0,0")
        while True:
            dline = self.textwidget.dlineinfo(i)
            if dline is None:
                break
            y = dline[1]
            linenum = str(i).split(".")[0]
            self.create_text(5, y, anchor="nw", text=linenum, font=("Arial", 11))
            i = self.textwidget.index("%s+1line" % i)


class CustomText(tk.Text):

    def __init__(self, *args, **kwargs):
        tk.Text.__init__(self, *args, **kwargs)

        self.tk.eval('''
            proc widget_proxy {widget widget_command args} {

                # call the real tk widget command with the real args
                set result [uplevel [linsert $args 0 $widget_command]]

                # generate the event for certain types of commands
                if {([lindex $args 0] in {insert replace delete}) ||
                    ([lrange $args 0 2] == {mark set insert}) || 
                    ([lrange $args 0 1] == {xview moveto}) ||
                    ([lrange $args 0 1] == {xview scroll}) ||
                    ([lrange $args 0 1] == {yview moveto}) ||
                    ([lrange $args 0 1] == {yview scroll})} {

                    event generate  $widget <<Change>> -when tail
                }

                # return the result from the real widget command
                return $result
            }
            ''')
        self.tk.eval('''
            rename {widget} _{widget}
            interp alias {{}} ::{widget} {{}} widget_proxy {widget} _{widget}
        '''.format(widget=str(self)))

        self.comment = False
        self.bind("<Tab>", self.indent)
    
    def indent(self, arg):
        self.insert(tk.INSERT, " " * tabSpace)
        return 'break'

    def highlight_pattern(self, pattern, tag, regex, start="1.0", end="end"):
        '''Apply the given tag to all text that matches the given pattern

        If 'regexp' is set to True, pattern will be treated as a regular
        expression.
        '''
        start = self.index(start)
        end = self.index(end)
        self.mark_set("matchStart", start)
        self.mark_set("matchEnd", start)
        self.mark_set("searchLimit", end)

        count = tk.IntVar()
        while True:
            index = self.search(pattern, "matchEnd", "searchLimit",
                                count=count, regexp=regex)
            if index == "":
                break
            self.mark_set("matchStart", index)
            self.mark_set("matchEnd", "%s+%sc" % (index, count.get()))
            self.tag_add(tag, "matchStart", "matchEnd")

    def copy(self):
        self.clipboard_clear()
        text = self.get("sel.first", "sel.last")
        self.clipboard_append(text)
    
    def configureBackground(self, background):
        self.configure(bg=background)

class Tab:

    def __init__(self, parent, filename, parentwindow):
        self.content = ""
        self.previousContent = ""
        self.parentwindow = parentwindow

        tabNoBorder = ttk.Style()
        tabNoBorder.layout("Tab",
                           [('Notebook.tab', {'sticky': 'nswe', 'children':
                                              [('Notebook.padding', {'side': 'top', 'sticky': 'nswe', 'children':
                                                                     [('Notebook.label', {
                                                                       'side': 'top', 'sticky': ''})],
                                                                     })],
                                              })]
                           )

        self.parent = parent
        self.filename = filename

        self.tab1 = ttk.Frame(parent, style="Tab")

        try:
            if wraptype == "word":
                self.text = CustomText(self.tab1, bd=0, font=("Lucida Console", 11), undo=True, background=themeColors[0].strip(), foreground=themeColors[1].strip(),
                                   insertbackground=themeColors[2].strip(), wrap=tk.WORD)
            else:
                self.text = CustomText(self.tab1, bd=0, font=("Lucida Console", 11), undo=True, background=themeColors[0].strip(), foreground=themeColors[1].strip(),
                                   insertbackground=themeColors[2].strip(), wrap=tk.CHAR)
        except:
            if wraptype == "word":
                self.text = CustomText(self.tab1, bd=0, font=(
                    "Lucida Console", 11), undo=True, background="#454545", foreground="#FAFAFA", insertbackground="#FAFAFA", wrap=tk.WORD)
            else:
                self.text = CustomText(self.tab1, bd=0, font=(
                    "Lucida Console", 11), undo=True, background="#454545", foreground="#FAFAFA", insertbackground="#FAFAFA", wrap=tk.CHAR)                

        self.row = "0"
        self.column = "0"
        self.startCol = 0

        self.vsb = ttk.Scrollbar(self.tab1, orient=tk.VERTICAL)
        self.text.configure(yscrollcommand=self.vsb.set)
        self.vsb.configure(command=self.text.yview)

        self.linenumbers = TextLineNumbers(self.tab1, width=64)
        self.linenumbers.attach(self.text)

        self.vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.linenumbers.pack(side="left", fill="y")
        self.text.pack(side="right", fill="both", expand=True)

        fileparts = filename.split("/")
        parent.add(self.tab1, text=fileparts[len(fileparts)-1])

        self.fileOpened = "Untitled Document"

        try:
            if "Untitled Document" != filename:
                self.fileOpened = filename
                contentStuff = ""
                
                with open(filename, 'r') as file:
                    for i in file.readlines():
                        contentStuff += i
                    
                self.text.insert("0.0", contentStuff)
                self.highlight("arg")
        except:
            pass

        self.text.bind("<<Change>>", self._on_change)
        self.text.bind("<Configure>", self._on_change)
        self.text.bind("<KeyRelease>", self.keypress)
        self.text.bind("<Button-1>", self.keypress)

        self.parent = parent

        self.configureTags()

    def clearText(self):
        self.text.delete(0.0, tk.END)
        self.fileName = "Untitled Document"

    def configureTags(self):
        try:
            self.text.tag_configure("Token.Keyword", foreground=themeColors[3].strip())
            self.text.tag_configure("Token.Keyword.Constant", foreground=themeColors[4].strip())
            self.text.tag_configure(
                "Token.Keyword.Declaration", foreground=themeColors[5].strip())
            self.text.tag_configure(
                "Token.Keyword.Namespace", foreground=themeColors[6].strip())
            self.text.tag_configure("Token.Keyword.Pseudo", foreground=themeColors[7].strip())
            self.text.tag_configure("Token.Keyword.Reserved", foreground=themeColors[8].strip())
            self.text.tag_configure("Token.Keyword.Type", foreground=themeColors[9].strip())

            self.text.tag_configure("Token.Name.Class", foreground=themeColors[10].strip())
            self.text.tag_configure("Token.Name.Exception", foreground=themeColors[11].strip())
            self.text.tag_configure("Token.Name.Function", foreground=themeColors[12].strip())
            self.text.tag_configure("Token.Name.Tag", foreground=themeColors[13].strip())
            self.text.tag_configure("Token.Name.Builtin", foreground=themeColors[14].strip())

            self.text.tag_configure("Token.Operator.Word", foreground=themeColors[15].strip())

            self.text.tag_configure("Token.Comment", foreground=themeColors[16].strip())

            self.text.tag_configure("Token.Literal.String", foreground=themeColors[17].strip())
            self.text.tag_configure(
                "Token.Literal.Number.Integer", foreground=themeColors[18].strip())
            self.text.tag_configure(
                "Token.Literal.Number.Bin", foreground=themeColors[19].strip())
            self.text.tag_configure(
                "Token.Literal.Number.Float", foreground=themeColors[20].strip())
            self.text.tag_configure(
                "Token.Literal.Number.Hex", foreground=themeColors[21].strip())
            self.text.tag_configure(
                "Token.Literal.Number.Integer.Long", foreground=themeColors[22].strip())
            self.text.tag_configure(
                "Token.Literal.Number.Oct", foreground=themeColors[23].strip())
        except:
            self.text.tag_configure("Token.Keyword", foreground="#69A2DB")
            self.text.tag_configure("Token.Keyword.Constant", foreground="#69A2DB")
            self.text.tag_configure(
                "Token.Keyword.Declaration", foreground="#69A2DB")
            self.text.tag_configure(
                "Token.Keyword.Namespace", foreground="#D771D7")
            self.text.tag_configure("Token.Keyword.Pseudo", foreground="#69A2DB")
            self.text.tag_configure("Token.Keyword.Reserved", foreground="#69A2DB")
            self.text.tag_configure("Token.Keyword.Type", foreground="#69A2DB")

            self.text.tag_configure("Token.Name.Class", foreground="#8686D6")
            self.text.tag_configure("Token.Name.Exception", foreground="#8686D6")
            self.text.tag_configure("Token.Name.Function", foreground="#85D6FF")
            self.text.tag_configure("Token.Name.Tag", foreground="#8686D6")
            self.text.tag_configure("Token.Name.Builtin", foreground="#8686D6")

            self.text.tag_configure("Token.Operator.Word", foreground="#29A6CF")

            self.text.tag_configure("Token.Comment", foreground="#FF8A8A")

            self.text.tag_configure("Token.Literal.String", foreground="#5CA65C")
            self.text.tag_configure(
                "Token.Literal.Number.Integer", foreground="#FF7DBD")
            self.text.tag_configure(
                "Token.Literal.Number.Bin", foreground="#ACC3F2")
            self.text.tag_configure(
                "Token.Literal.Number.Float", foreground="#7DA1EB")
            self.text.tag_configure(
                "Token.Literal.Number.Hex", foreground="#5C8AE6")
            self.text.tag_configure(
                "Token.Literal.Number.Integer.Long", foreground="#7DA1EB")
            self.text.tag_configure(
                "Token.Literal.Number.Oct", foreground="#5C8AE6")

    def deafultHighlight(self, argument):
        self.content = self.text.get("1.0", tk.END)
        self.lines = self.content.split("\n")

        self.row = self.text.index(tk.INSERT).split(".")[0]
        self.column = self.text.index(tk.INSERT).split(".")[1]

        self.text.mark_set("range_start", self.row + ".0")
        data = self.text.get(self.row + ".0", self.row +
                             "." + str(len(self.lines[int(self.row) - 1])))

        tokens = ["Token.Keyword", "Token.Keyword.Constant", "Token.Keyword.Declaration", "Token.Keyword.Namespace", "Token.Keyword.Pseudo",
        "Token.Keyword.Reserved", "Token.Keyword.Type", "Token.Name.Class", "Token.Name.Exception", "Token.Name.Function",
        "Token.Name.Tag", "Token.Name.Builtin", "Token.Operator.Word", "Token.Comment", "Token.Literal.String", "Token.Literal.Number.Integer",
        "Token.Literal.Number.Bin", "Token.Literal.Number.Float", "Token.Literal.Number.Hex", "Token.Literal.Number.Integer.Long",
        "Token.Literal.Number.Oct"]

        for token in tokens:
            self.text.tag_remove(token, self.row+".0", self.row +
                             "." + str(len(self.lines[int(self.row) - 1])))

        for token, content in lex(data, PythonLexer()):
            self.text.mark_set("range_end", "range_start + %dc" % len(content))
            self.text.tag_add(str(token), "range_start", "range_end")
            self.text.mark_set("range_start", "range_end")

    def specificHighlight(self, start, end):
        self.content = self.text.get("1.0", tk.END)
        self.lines = self.content.split("\n")

        self.row = start
        self.column = end

        self.text.mark_set("range_start", self.row + ".0")
        data = self.text.get(self.row + ".0", self.row +
                             "." + str(len(self.lines[int(self.row) - 1])))

        for token, content in lex(data, PythonLexer()):
            self.text.mark_set("range_end", "range_start + %dc" % len(content))
            self.text.tag_add(str(token), "range_start", "range_end")
            self.text.mark_set("range_start", "range_end")

    def highlight(self, argument):
        self.content = self.text.get("1.0", tk.END)

        if (self.previousContent != self.content):
            self.text.mark_set("range_start", "1.0")
            data = self.text.get("1.0", self.text.index(tk.INSERT))

            for token, content in lex(data, PythonLexer()):
                self.text.mark_set(
                    "range_end", "range_start + %dc" % len(content))
                self.text.tag_add(str(token), "range_start", "range_end")
                self.text.mark_set("range_start", "range_end")

        self.previousContent = self.text.get("1.0", tk.END)

    def individualHighlight(self, startPos, endPos, color):
        self.text.tag_configure("highlightedWord", background=color)
        self.text.tag_add("highlightedWord", startPos, endPos)

    def clearPreviousHighlight(self, startPos, endPos, color):
        self.text.tag_remove("clearHighlight", startPos, endPos)
        self.text.tag_remove("highlightedWord", startPos, endPos)

    def clearAll(self, color):
        self.text.tag_delete("highlight")
        self.text.tag_delete("clearHighlight")
        self.text.tag_delete("highlightedWord")

    def changeTheme(self, tagColors):
        self.clearAll("asdf")

        try:
            self.text.tag_configure("Token.Keyword", foreground=tagColors[0])
            self.text.tag_configure("Token.Keyword.Constant", foreground=tagColors[1])
            self.text.tag_configure(
                "Token.Keyword.Declaration", foreground=tagColors[2])
            self.text.tag_configure(
                "Token.Keyword.Namespace", foreground=tagColors[3])
            self.text.tag_configure("Token.Keyword.Pseudo", foreground=tagColors[4])
            self.text.tag_configure("Token.Keyword.Reserved", foreground=tagColors[5])
            self.text.tag_configure("Token.Keyword.Type", foreground=tagColors[6])

            self.text.tag_configure("Token.Name.Class", foreground=tagColors[7])
            self.text.tag_configure("Token.Name.Exception", foreground=tagColors[8])
            self.text.tag_configure("Token.Name.Function", foreground=tagColors[9])
            self.text.tag_configure("Token.Name.Tag", foreground=tagColors[10])
            self.text.tag_configure("Token.Name.Builtin", foreground=tagColors[11])

            self.text.tag_configure("Token.Operator.Word", foreground=tagColors[12])

            self.text.tag_configure("Token.Comment", foreground=tagColors[13])

            self.text.tag_configure("Token.Literal.String", foreground=tagColors[14])
            self.text.tag_configure(
                "Token.Literal.Number.Integer", foreground=tagColors[15])
            self.text.tag_configure(
                "Token.Literal.Number.Bin", foreground=tagColors[16])
            self.text.tag_configure(
                "Token.Literal.Number.Float", foreground=tagColors[17])
            self.text.tag_configure(
                "Token.Literal.Number.Hex", foreground=tagColors[18])
            self.text.tag_configure(
                "Token.Literal.Number.Integer.Long", foreground=tagColors[19])
            self.text.tag_configure(
                "Token.Literal.Number.Oct", foreground=tagColors[20])
            self.text.configureBackground(tagColors[21])
            self.text.configure(fg=tagColors[22])
            self.text.configure(insertbackground=tagColors[23])
        except Exception as e:
            pass

    def displayFile(self, text):
        self.text.delete(0.0, tk.END)
        self.text.insert(0.0, text)
        self.highlight("Positional Argument")

    def getContent(self):
        return self.text.get(0.0, tk.END)

    def keypress(self, argument):
        self.deafultHighlight("argument")
        self.parent._nametowidget(self.parent.winfo_parent()).updateBottomLabel(self.text.index(
            tk.INSERT).split(".")[0], self.text.index(tk.INSERT).split(".")[1], len(self.text.get("1.0", tk.END)), "Python")
        self.text.tag_delete("Error")

    def replace(self, content):
        self.text.delete(1.0, tk.END)
        self.text.insert(1.0, content)

    def _on_change(self, event):
        self.linenumbers.redraw()

    def configureFont(self, fontFamily, fontSize):
        self.text.config(font=(fontFamily, fontSize))


class Arshi(tk.Frame):

    def __init__(self, *args, **kwargs):
        tk.Frame.__init__(self, *args, **kwargs)
        self.tabs = []

        self.notebook = ttk.Notebook(self)
        self.fileName = ""
        self.content = ""

        self.highlightColor = "#000000"

        self.bottomlabel()
        self.createtext()
        self.menubar()

        self.instance = 0

        self.bind_all("<Control-n>", self.newFile)
        self.bind_all("<Control-o>", self.openFile)
        self.bind_all("<Control-s>", self.saveFile)
        self.bind_all("<Control-S>", self.saveAsFile)
        self.bind_all("<Control-q>", self.close)

        self.bind_all("<Control-t>", self.addtab)
        self.bind_all("<Control-w>", self.removetab)
        
        self.bind_all("<Control-f>", self.search)

        self.bind_all("<Control-i>", self.indent)

        self.bind_all("<Control-e>", self.changeFont)

        self.bind_all("<Control-k>", self.nextTab)
        self.bind_all("<Control-space>", self.previousTabExtra)

        self.bind_all("<Control-r>", self.minimalMode)
        self.bind_all("<Control-d>", self.standardMode)

        self.bind_all("<Control-l>", self.gotoCursor)

        self.bind_all("<F11>", self.toggleScreenSize)

        self.bind_all("<F5>", self.runFile)
        self.bind_all("<F6>", self.toggleLineNumbers)
        self.bind_all("<F7>", self.toggleBottomLabel)

        self.bind_all("<F1>", self.jumpToTop)
        self.bind_all("<F2>", self.jumpToBottom)

        self.lineNumbers = False
        self.bottomLabel = False
        self.fullScreen = False

        self.syntaxHighlighting = True

        self.previousColor = ""

        self.standardColor = "#66FF66"

        self.previousRange = -4463

        self.previousCaseOrNot = False
        self.previousRegex = False

        self.previousContent = ""

        self.language = "Plain Text"
        self.font = "Consolas"
        self.fontSize = "11"

        self.contextMenu = tk.Menu(self, font=("Consolas", 9), tearoff=0)
        self.contextMenu.add_command(label="Undo", command=self.undo)
        self.contextMenu.add_command(label="Redo", command=self.redo)
        self.contextMenu.add_separator()
        self.contextMenu.add_command(label="Cut", command=self.cut)
        self.contextMenu.add_command(label="Copy", command=self.copy)
        self.contextMenu.add_command(label="Paste", command=self.paste)
        self.contextMenu.add_separator()
        self.contextMenu.add_command(label="Remove Tab", command=lambda: self.removetab("arg"))

        try:
            with open("resources/openfiles.txt", 'r') as file:
                filesOpened = file.readlines()

            filesOpened = filter(None, filesOpened) # fast
            filterFiles = [x for x in filesOpened]
            for i in range(0, len(filterFiles)):
                self.addExistingTab(filterFiles[i].strip())

            if len(self.tabs) > 1:
                self.tabs.pop(0)
                self.notebook.forget(0)
        except:
            pass

        try:
            with open("resources/selectedfiles.txt", 'r') as file:
                selectedFiles = file.read()

            self.notebook.select(int(selectedFiles))
        except:
            pass

        try:
            with open("resources/fonts.txt", 'r') as file:
                fonts = file.read()
            
            for i in range(0, self.notebook.index("end")):
                self.tabs[i].configureFont(fonts.split("\n")[0], fonts.split("\n")[1])

            self.font = fonts.split("\n")[0]
            self.fontSize = fonts.split("\n")[1]
        except Exception as e:
            pass

        self.bind_all("<Button-3>", self.popup)

    def popup(self, event):
        self.contextMenu.post(event.x_root, event.y_root)

    def addExistingTab(self, fileName):
        try:
            existingFileNames = fileName.split("\\")
            t = Tab(self.notebook, existingFileNames[len(existingFileNames) - 1], self)
            self.tabs.append(t)
        except FileNotFoundError:
            tkinter.messagebox.showinfo("File Not Found", "File doesn't exist")
        except:
            tkinter.messagebox.showinfo("Unexpected Error", "An unexpected error occured")
        
    def createtext(self):
        self.notebook.pack(fill=tk.BOTH, expand=True)
        t = Tab(self.notebook, "Untitled Document", self)
        self.tabs.append(t)

    def menubar(self):
        self.menu = tk.Menu(self)
        self.master.config(menu=self.menu)

        self.fileMenu = tk.Menu(self.menu, font=("Consolas",9), tearoff=0)
        self.fileMenu.add_command(
            label="New File                 Ctrl+N", command=lambda: self.newFile("arg"))
        self.fileMenu.add_command(
            label="Open File                Ctrl+O", command=lambda: self.openFile("arg"))
        self.fileMenu.add_command(
            label="Save File                Ctrl+S", command=lambda: self.saveFile("arg"))
        self.fileMenu.add_command(
            label="Save As File       Ctrl+Shift+S", command=lambda: self.saveAsFile("arg"))
        self.fileMenu.add_separator()
        self.fileMenu.add_command(
            label="New Tab                  Ctrl+T", command=lambda: self.addtab("arg"))
        self.fileMenu.add_command(
            label="New Window", command=lambda: self.newWindow("arg"))
        self.fileMenu.add_command(
            label="Close Tab                Ctrl+W", command=lambda: self.removetab("arg"))
        self.fileMenu.add_separator()
        self.fileMenu.add_command(
            label="Next Tab                 Ctrl+K", command=lambda: self.nextTab("arg"))
        self.fileMenu.add_command(
            label="Previous Tab         Ctrl+Space", command=self.previousTab)
        self.fileMenu.add_separator()
        self.fileMenu.add_command(
            label="Exit                     Ctrl+Q", command=lambda: self.close("arg"))
        self.menu.add_cascade(label="File", menu=self.fileMenu)

        self.editMenu = tk.Menu(self.menu, font=("Consolas", 9), tearoff=0)
        self.editMenu.add_command(
            label="Find and Replace           Ctrl+F", command=lambda: self.search("arg"))
        self.editMenu.add_separator()
        self.editMenu.add_command(
            label="Remove Trailing Space", command=self.trail)
        self.editMenu.add_separator()
        self.editMenu.add_command(
            label="Copy                       Ctrl+C", command=self.copy)
        self.editMenu.add_command(
            label="Paste                      Ctrl+V", command=self.paste)
        self.editMenu.add_command(
            label="Cut                        Ctrl+X", command=self.cut)
        self.editMenu.add_separator()
        self.editMenu.add_command(
            label="Undo                       Ctrl+Z", command=self.undo)
        self.editMenu.add_command(
            label="Redo                       Ctrl+Y", command=self.redo)
        self.editMenu.add_separator()
        self.editMenu.add_command(
            label="Jump to top                    F1", command=lambda: self.jumpToTop("arg"))
        self.editMenu.add_command(
            label="Jump to end                    F2", command=lambda: self.jumpToBottom("arg"))
        self.editMenu.add_command(
            label="Goto Cursor                Ctrl+L", command=lambda: self.gotoCursor("arg"))
        self.editMenu.add_separator()
        self.editMenu.add_command(label="Format/Convention",
                                  command=lambda: self.formatAndConventionalize("arg"))
        self.editMenu.add_separator()
        self.editMenu.add_command(label="Merge", command=self.merge)
        self.editMenu.add_separator()
        self.editMenu.add_command(label="Encrypt File (Advanced User)", command=self.encryptFile)
        self.editMenu.add_command(label="Decrypt File (Advanced User)", command=self.decryptFile)
        self.menu.add_cascade(label="Edit", menu=self.editMenu)

        self.configMenu = tk.Menu(
            self.menu, font=("Consolas", 9), tearoff=0)
        self.configMenu.add_command(
            label="Font                         Ctrl+E", command=lambda: self.changeFont("arg"))
        self.configMenu.add_separator()
        self.configMenu.add_command(
            label="Theme Syntax", command=self.chooseTheme)
        self.configMenu.add_separator()
        self.configMenu.add_command(label="Wrap", command=self.wrap)
        self.configMenu.add_command(
            label="Indentation                  Ctrl+I", command=lambda: self.indent("arg"))
        self.menu.add_cascade(label="Option", menu=self.configMenu)

        self.viewMenu = tk.Menu(self.menu, font=("Consolas", 9), tearoff=0)
        self.viewMenu.add_command(
            label="Toggle Language and Position Label    F6", command=lambda: self.toggleBottomLabel("arg"))
        self.viewMenu.add_command(
            label="Toggle Line Numbers                   F7", command=lambda: self.toggleLineNumbers("arg"))
        self.viewMenu.add_separator()
        self.viewMenu.add_command(
            label="Minimal Mode                      Ctrl+R", command=lambda: self.minimalMode("arg"))
        self.viewMenu.add_command(
            label="Standard Mode                     Ctrl+D", command=lambda: self.standardMode("arg"))
        self.viewMenu.add_command(
            label="Toggle Fullscreen                    F11", command=lambda: self.toggleScreenSize("arg"))
        self.menu.add_cascade(label="View", menu=self.viewMenu)

        self.runMenu = tk.Menu(self.menu, font=("Consolas", 9), tearoff=0)
        self.runMenu.add_command(
            label="Run Python              F5", command=lambda: self.runFile("arg"))
        self.runMenu.add_command(
            label="Run in Browser", command=self.runBrowser)
        self.runMenu.add_command(label="Debug", command=self.debugMode)
        self.menu.add_cascade(label="Run", menu=self.runMenu)

        self.helpMenu = tk.Menu(self.menu, font=("Consolas", 9), tearoff=0)
        self.helpMenu.add_command(label="About", command=self.about)
        self.menu.add_cascade(label="Help", menu=self.helpMenu)

    def runBrowser(self):
        tkinter.messagebox.showinfo("Running in Browser", "Running Python Django files from Arshi is only available on Arshi+, which will be released this winter break.")

    def newWindow(self, arg):
        tkinter.messagebox.showinfo("Multi-Windows", "Multi-Window editing is only available on Arshi+, which will be released this winter break.")

    def jumpToTop(self, arg):
        tabIndex = self.notebook.index(self.notebook.select())
        self.tabs[tabIndex].text.see("0.0")
        self.tabs[tabIndex]._on_change("arg")

    def jumpToBottom(self, arg):
        tabIndex = self.notebook.index(self.notebook.select())
        self.tabs[tabIndex].text.see(tk.END)
        self.tabs[tabIndex]._on_change("arg")

    def openFolder(self, arg):
        pass

    def wrap(self):
        wrapContent = tk.Toplevel()
        wrapContent.resizable(0, 0)
        wrapContent.title("Wrap")

        self.wrapLabel = tk.Label(wrapContent, text="Arshi supports both line and word wrapping", font=("Consolas", 9)).pack()

        self.typeWrap = tk.IntVar()
        lineWrapButton = tk.Radiobutton(wrapContent, text="Line Wrap", variable=self.typeWrap, value=1, font=("Consolas", 9))
        lineWrapButton.pack()

        wordWrapButton = tk.Radiobutton(wrapContent, text="Word Wrap", variable=self.typeWrap, value=2, font=("Consolas", 9))
        wordWrapButton.pack()

        self.wrapCommand = tk.Button(wrapContent, text="Ok", font=("Consolas", 9), command=self.wrapHandler)
        self.wrapCommand.pack(fill=tk.X)

    def wrapHandler(self):
        global wraptype
        
        if self.typeWrap.get() == 2:
            for i in range(0, self.notebook.index("end")):
                self.tabs[i].text.configure(wrap=tk.WORD)
            wraptype = "word"
        else:
            for i in range(0, self.notebook.index("end")):
                self.tabs[i].text.configure(wrap=tk.CHAR)
            wraptype = "char"

    def indent(self, arg):
        indentContent = tk.Toplevel()
        indentContent.resizable(0, 0)
        indentContent.title("Indent")

        self.indentContent = tk.Label(indentContent, text="Enter the equivalent of a tab in spaces (1-24)")
        self.indentContent.pack()

        self.indentEntry = tk.Entry(indentContent)
        self.indentEntry.pack(fill=tk.X)
        
        self.indentCommand = tk.Button(indentContent, text="Ok", font=("Consolas", 9), command=self.changeIndentation).pack(fill=tk.X)

    def changeIndentation(self):
        global tabSpace
        
        try:
            previousTabSpace = tabSpace
            
            if int(self.indentEntry.get()) > 0 and int(self.indentEntry.get()) >= 1 and int(self.indentEntry.get()) <= 24:
                tabSpace = int(self.indentEntry.get())

                for i in range(0, self.notebook.index("end")):
                    self.content = self.tabs[i].getContent().replace(previousTabSpace * " ", tabSpace * " ")
                    self.tabs[i].replace(self.content)
                    self.tabs[i].highlight("argument")
        except Exception as e:
            pass

    def languageWindow(self, arg):
        languageSwitcher = tk.Toplevel()
        languageSwitcher.resizable(0, 0)
        languageSwitcher.title("Language")

        languageLabel = tk.Label(languageSwitcher, text="Choose or type in a text format / language / math system")
        languageLabel.pack()

        languageEntry = ttk.Combobox(languageSwitcher)
        languageEntry.pack()

    def indentLine(self):
        tabIndex = self.notebook.index(self.notebook.select())
        self.tabs[tabIndex].text.insert(self.tabs[tabIndex].text.index(
            tk.INSERT).split(".")[0] + ".0", " " * tabSpace)

    def indentDocument(self):
        tabIndex = self.notebook.index(self.notebook.select())
        lines = self.tabs[tabIndex].getContent().split("\n")
        modifiedLines = []

        for i in range(len(lines)):
            line = " " * tabSpace + lines[i]
            modifiedLines.append(line)

        newString = ""

        for i in range(len(modifiedLines)):
            newString += modifiedLines[i]
            newString += "\n"

        self.tabs[tabIndex].replace(newString)
        self.tabs[tabIndex].highlight("arg")

    def undo(self):
        tabIndex = self.notebook.index(self.notebook.select())
        self.tabs[tabIndex].text.edit_undo()

    def redo(self):
        tabIndex = self.notebook.index(self.notebook.select())
        self.tabs[tabIndex].text.edit_redo()

    def cut(self):
        tabIndex = self.notebook.index(self.notebook.select())
        self.tabs[tabIndex].text.copy()
        self.tabs[tabIndex].text.delete("sel.first", "sel.last")

    def copy(self):
        tabIndex = self.notebook.index(self.notebook.select())
        self.tabs[tabIndex].text.clipboard_clear()
        text = self.tabs[tabIndex].text.get("sel.first", "sel.last")
        self.tabs[tabIndex].text.clipboard_append(text)

    def paste(self):
        tabIndex = self.notebook.index(self.notebook.select())
        text = self.tabs[tabIndex].text.selection_get(selection='CLIPBOARD')
        self.tabs[tabIndex].text.insert('insert', text)

    def formatAndConventionalize(self, arg):
        tabIndex = self.notebook.index(self.notebook.select())
        text = self.tabs[tabIndex].getContent()
        correctedText = autopep8.fix_code(text)
        self.tabs[tabIndex].replace(correctedText)
        self.tabs[tabIndex].highlight("arg")

    def runFile(self, arg):
        try:
            exec(open(self.tabs[self.notebook.index(self.notebook.select())].fileOpened).read())
        except SyntaxError as err:
            error_class = err.__class__.__name__
            detail = err.args[0]
            line_number = err.lineno

            tabIndex = self.notebook.index(self.notebook.select())
            self.tabs[tabIndex].text.tag_configure(
                "Error", background="#FFA48D")
            self.tabs[tabIndex].text.tag_add("Error", str(
                line_number) + ".0", str(line_number) + ".0 lineend")

            tkinter.messagebox.showinfo("SyntaxError", str(err))
        except FileNotFoundError as err:
            tkinter.messagebox.showinfo(
                "FileNotFoundError", "Please save your file first before running your program.")
        except Exception as err:
            error_class = err.__class__.__name__
            detail = err.args[0]
            cl, exc, tb = sys.exc_info()
            line_number = traceback.extract_tb(tb)[-1][1]

            tabIndex = self.notebook.index(self.notebook.select())
            self.tabs[tabIndex].text.tag_configure(
                "Error", background="#FFA48D")
            self.tabs[tabIndex].text.tag_add("Error", str(
                line_number) + ".0", str(line_number) + ".0 lineend")

            tkinter.messagebox.showinfo(type(err).__name__, str(
                err) + " (line " + str(line_number) + ")")
        else:
            return

    def toggleLineNumbers(self, arg):
        self.lineNumbers = not self.lineNumbers

        if self.lineNumbers:
            for i in range(0, self.notebook.index("end")):
                tabIndex = i
                self.tabs[tabIndex].linenumbers.pack_forget()
        else:
            for i in range(0, self.notebook.index("end")):
                tabIndex = i
                self.tabs[tabIndex].linenumbers.pack(side="left", fill="y")

    def toggleBottomLabel(self, arg):
        self.bottomLabel = not self.bottomLabel

        if self.bottomLabel:
            self.positionAndLanguage.pack_forget()
        else:
            self.positionAndLanguage.pack(fill=tk.X, side=tk.BOTTOM)

    def minimalMode(self, arg):
        if self.fullScreen:
            self.master.attributes("-fullscreen", True)
        else:
            self.master.attributes("-fullscreen", False)

        for i in range(0, self.notebook.index("end")):
            tabIndex = i
            self.tabs[tabIndex].linenumbers.pack_forget()

        self.positionAndLanguage.pack_forget()

    def standardMode(self, arg):
        if self.fullScreen:
            self.master.attributes("-fullscreen", True)
        else:
            self.master.attributes("-fullscreen", False)

        for i in range(0, self.notebook.index("end")):
            tabIndex = i
            self.tabs[tabIndex].linenumbers.pack(side="left", fill="y")

        self.positionAndLanguage.pack(fill=tk.X, side=tk.BOTTOM)

    def chooseTheme(self):
        themeLevel = tk.Toplevel()

        asdf = tk.Label(themeLevel, text="Use hexadecimals and Tcl string colors.\nThe syntax is listed in the order below:\n", font=("Consolas", 9))
        asdf.pack()

        stuff = ["Background", "Foreground", "Cursor Color", "Token.Keyword", "Token.Keyword.Constant", "Token.Keyword.Declaration", "Token.Keyword.Namespace", "Token.Keyword.Pseudo",
        "Token.Keyword.Reserved", "Token.Keyword.Type", "Token.Name.Class", "Token.Name.Exception", "Token.Name.Function",
        "Token.Name.Tag", "Token.Name.Builtin", "Token.Operator.Word", "Token.Comment", "Token.Literal.String", "Token.Literal.Number.Integer",
        "Token.Literal.Number.Bin", "Token.Literal.Number.Float", "Token.Literal.Number.Hex", "Token.Literal.Number.Integer.Long",
        "Token.Literal.Number.Oct"]

        for i in stuff:
            asdf2 = tk.Label(themeLevel, text=i, font=("Consolas", 9)).pack()

    def gotoCursor(self, arg):
        tabIndex = self.notebook.index(self.notebook.select())
        self.tabs[tabIndex].text.see(tk.INSERT)
        self.tabs[tabIndex]._on_change("arg")

    def toggleScreenSize(self, arg):
        self.fullScreen = not self.fullScreen
        self.master.attributes("-fullscreen", self.fullScreen)

    def trail(self):
        tabIndex = self.notebook.index(self.notebook.select())
        self.content = self.tabs[tabIndex].getContent()
        self.content = self.content.strip()
        self.tabs[tabIndex].replace(self.content)
        self.tabs[tabIndex].highlight("arg")

    def encryptFile(self):
        tkinter.messagebox.showinfo("Encryption", "Encryption is only available on Arshi+, which will be released this winter break")

    def decryptFile(self):
        tkinter.messagebox.showinfo("Decrpytion", "Decrpytion is only available on Arshi+, which will be released this winter break")

    def about(self):
        self.aboutMessage = tk.Toplevel()
        self.aboutMessage.title("About")
        self.aboutMessage.resizable(0, 0)
        self.about = tk.Message(self.aboutMessage, text="  Arshi is a practical text editor designed for you to edit Python files efficiently\n\nArshi was coded through Python's Tk/Ttk/Tcl GUI toolkit.\n\nIt was "
                                + "developed by Henry Zhu. It might be hard for me to answer your questions directly, because I am a Freshman.\n\nWebsite: http://arshieditor.com\nEmail: henry.david.zhu@gmail.com\n", font=('Consolas', 9))
        self.credits = tk.Button(
            self.aboutMessage, text="Credits", command=self.creditsPage, font=('Consolas', 9))

        self.about.pack()

        self.credits.pack(fill=tk.X)

    def creditsPage(self):
        self.credits = tk.Toplevel()
        self.credits.title("Credits")
        self.credits.resizable(0, 0)

        self.informationPage = tk.Message(self.credits, text="The programming, and design of Arshi text editor was done by Henry Zhu.\n\nSpecial shoutout to the StackOverflow community, Daniweb community, Pygments,"
                                          + " as well as effbot.org for making this project possible.\n\nThe UI of Arshi was a hybrid of designs inspired by the minimal Python IDLE and other more "
                                          + "sophisticated text editors such as Vim, Notepad++ & Sublime Text.", font=('Consolas', 9))
        self.informationPage.pack()

    def searchProtocol(self):
        self.instance = 0

        tabIndex = self.notebook.index(self.notebook.select())
        self.pos = '1.0'
        self.finalPos = '1.0'
        self.previousPos = self.pos
        self.previousFinalPos = self.finalPos

        self.tabs[tabIndex].clearAll("#FFFFFF")

        self.searchMenu.destroy()

    def getColor(self):
        self.color = tkinter.colorchooser.askcolor(parent=self.searchMenu)[1]
        self.highlightLineEntry.insert(0, self.color)
        self.highlightColor = self.color

    def changeFont(self, arg):
        self.fontOption = tk.Toplevel()
        self.fontOption.resizable(0, 0)
        self.fontOption.title("Choose Font")

        self.selectFont = tk.Label(
            self.fontOption, text="Font Family: ", font=("Consolas", 9))
        self.selectFont.grid(row=0, columnspan=1)

        self.fontComboBox = ttk.Combobox(self.fontOption)
        self.fontComboBox['values'] = ("Arial", "Courier New", "Consolas", "Georgia", "Monaco", "MS Sans Serif", "MS Serif", "New York", "Lucida Console",
                                       "Lucida Grande", "Lucida Sans Unicode", "Tahoma", "Trebuchet MS", "Times New Roman", "Verdana")
        self.fontComboBox.current(2)
        self.fontComboBox.grid(row=0, column=1, columnspan=1)

        self.selectFontSize = tk.Label(
            self.fontOption, text="Font Size: ", font=("Consolas", 9))
        self.selectFontSize.grid(row=1, columnspan=1)

        self.fontSizeComboBox = ttk.Combobox(self.fontOption)
        self.fontSizeComboBox['values'] = (
            "8", "9", "10", "11", "12", "13", "14", "15", "16", "17", "18", "19", "20", "21", "22", "23", "24")
        self.fontSizeComboBox.current(3)
        self.fontSizeComboBox.grid(row=1, column=1, columnspan=1)

        self.fontProceed = tk.Button(self.fontOption, text="Ok", font=(
            "Consolas", 9), command=self.proceedWithFontChange)
        self.fontProceed.grid(row=2, column=0, columnspan=2, sticky='NSEW')

    def proceedWithFontChange(self):
        self.fontFamily = self.fontComboBox.get()
        self.fontSize = self.fontSizeComboBox.get()

        if self.fontFamily not in ["Arial", "Courier New", "Consolas", "Georgia", "Monaco", "MS Sans Serif", "MS Serif", "New York", "Lucida Console",
                                   "Lucida Grande", "Lucida Sans Unicode", "Tahoma", "Trebuchet MS", "Times New Roman", "Verdana"]:
            tkinter.messagebox.showinfo("Invalid Font Family", "Arshi supports the current font options: Arial, Courier New, Consolas, Geneva, Georgia, Monaco, MS Sans Serif, "
                                        + "MS Serif, New York, Lucida Console, Lucida Grande, Lucida Sans Unicode, Tahoma, Trebuchet MS, Times New Roman,"
                                        + " Verdana")
            self.fontOption.destroy()
        elif self.fontSize not in ["8", "9", "10", "11", "12", "13", "14", "15", "16", "17", "18", "19", "20", "21", "22", "23", "24"]:
            tkinter.messagebox.showinfo(
                "Invalid Font Size", "Arshi supports font sizes from 8px to 24px")
        else:
            tabIndex = self.notebook.index("end")

            for i in range(0, tabIndex):
                self.tabs[i].configureFont(self.fontFamily, int(self.fontSize))

        try:
            with open("resources/fonts.txt", 'w') as file:
                file.write(self.fontFamily + "\n" + self.fontSize)
        except:
            tkinter.messagebox.showinfo("Fonts File Missing or Corrupt", "The font data will not be cached.")

    def debugMode(self):
        tkinter.messagebox.showinfo("Debugging Mode", "Debugging will be available on Arshi+, an enhanced version of the base Arshi editor. Arshi+ will be released this "
                                    + "winter break.")

    def search(self, arg):
        self.searchMenu = tk.Toplevel()
        self.searchMenu.title("Search and Replace")
        self.searchMenu.geometry("545x205")
        self.searchMenu.resizable(0, 0)

        self.previousSearch = ""
        self.previousDirection = 0

        self.searchDirection = tk.Label(
            self.searchMenu, text=" String to search", anchor=tk.W, font=("Consolas", 9))
        self.entry = tk.Entry(self.searchMenu, width=30,
                              font=("Consolas", 9))

        self.replaceDirection = tk.Label(
            self.searchMenu, text=" String to replace", anchor=tk.W, font=("Consolas", 9))
        self.replace = tk.Entry(
            self.searchMenu, width=30, font=("Consolas", 9))

        self.searchOptions = tk.Label(
            self.searchMenu, text=" Search options", anchor=tk.W, font=("Consolas", 9))

        self.regex = tk.IntVar()
        self.regularExpression = tk.Checkbutton(
            self.searchMenu, text="Regex", variable=self.regex, anchor=tk.W, font=("Consolas", 9))

        self.matchcase = tk.IntVar()
        self.matchCase = tk.Checkbutton(
            self.searchMenu, text="Match Case", variable=self.matchcase, anchor=tk.W, font=("Consolas", 9))

        self.searchWay = tk.Label(
            self.searchMenu, text=" Search direction", anchor=tk.W, font=("Consolas", 9))

        self.direction = tk.IntVar()
        self.up = tk.Radiobutton(self.searchMenu, text="Down", variable=self.direction, value=1, font=(
            "Consolas", 9)).place(x=340, y=75, width=140)
        self.down = tk.Radiobutton(self.searchMenu, text="Up", variable=self.direction, value=2, font=(
            "Consolas", 9)).place(x=175, y=75, width=140)

        self.searchRange = tk.Label(
            self.searchMenu, text=" Search range", anchor=tk.W, font=("Consolas", 9))
        self.rangeEntry = tk.Entry(
            self.searchMenu, width=30, font=("Consolas", 9))

        self.searchButton = tk.Button(self.searchMenu, text="Search", font=(
            "Consolas", 9), command=lambda: self.continueSearch(self.entry.get(), self.rangeEntry.get()))

        self.searchClose = tk.Button(self.searchMenu, text="Replace", font=(
            "Consolas", 9), command=lambda: self.replaceAll(self.entry.get(), self.replace.get()))

        self.highlightLine = tk.Label(
            self.searchMenu, text=" Search color", anchor=tk.W, font=("Consolas", 9))
        self.highlightLineButton = tk.Button(self.searchMenu, text="Color", anchor=tk.W, font=(
            "Consolas", 9), command=self.getColor)
        self.highlightLineEntry = tk.Entry(
            self.searchMenu, width=30, font=("Consolas", 9))

        self.searchMenu.protocol("WM_DELETE_WINDOW", self.searchProtocol)

        self.searchDirection.place(x=0, y=0, width=200)
        self.replaceDirection.place(x=0, y=25, width=200)
        self.searchOptions.place(x=0, y=50, width=200)
        self.searchWay.place(x=0, y=75, width=200)
        self.searchRange.place(x=0, y=100, width=140)
        self.rangeEntry.place(x=220, y=100, width=325)
        self.highlightLine.place(x=0, y=130, width=145)
        self.highlightLineButton.place(x=155, y=125)
        self.highlightLineEntry.place(x=220, y=125, width=325)
        self.searchButton.place(x=20, y=160, width=200)
        self.searchClose.place(x=325, y=160, width=200)

        self.entry.place(x=220, y=0, width=325)
        self.replace.place(x=220, y=25, width=325)
        self.matchCase.place(x=220, y=50, width=140)
        self.regularExpression.place(x=375, y=50, width=140)

    def replaceAll(self, replaceTerm, newTerm):
        if len(replaceTerm) > 0:
            tabIndex = self.notebook.index(self.notebook.select())
            self.content = self.tabs[
                tabIndex].getContent().replace(replaceTerm, newTerm)
            self.tabs[tabIndex].replace(self.content)
            self.tabs[tabIndex].highlight("argument")

    def nextTab(self, arg):
        tabIndex = self.notebook.index(self.notebook.select())
        tabIndex += 1

        if tabIndex == self.notebook.index("end"):
            tabIndex = 0

        self.notebook.select(tabIndex)

    def previousTab(self):
        tabIndex = self.notebook.index(self.notebook.select())
        tabIndex -= 1

        if tabIndex + 1 == 0:
            tabIndex = self.notebook.index("end") - 1

        self.notebook.select(tabIndex)

    def previousTabExtra(self, arg):
        self.previousTab()

    def merge(self):
        self.mergePage = tk.Toplevel()
        self.mergePage.resizable(0, 0)
        self.mergePage.title("Merge Tabs")
        self.instruction = tk.Label(self.mergePage, text="Separate tab #s by commas: 1, 2, 3, 4").pack()
        self.mergeEntry = tk.Entry(self.mergePage)
        self.mergeEntry.pack(fill=tk.X)
        self.instruction2 = tk.Label(self.mergePage, text="Tab # to merge files in (starting from index 1)").pack()
        self.mergeTargetEntry = tk.Entry(self.mergePage)
        self.mergeTargetEntry.pack(fill=tk.X)
        self.mergeButton = tk.Button(self.mergePage, text="Merge", command=self.mergeFunction).pack(fill=tk.X)

    def mergeFunction(self):
        try:
            self.tabList = self.mergeEntry.get().split(",")
            self.modifiedTabList = [tab.strip(' ') for tab in self.tabList]
            self.integerModifiedTabList = self.modifiedTabList
            self.integerModifiedTabList = map(int, self.integerModifiedTabList)
            self.integerModifiedTabList = list(set(self.integerModifiedTabList))
            self.mergeTarget = int(self.mergeTargetEntry.get()) - 1
            
            if self.mergeTarget in self.integerModifiedTabList:
                self.integerModifiedTabList.remove(self.mergeTarget)

            text = ""

            for i in self.integerModifiedTabList:
                text += self.tabs[i - 1].getContent()
                text += "\n"
            
            self.tabs[self.mergeTarget].replace(text)
            self.tabs[self.mergeTarget].highlight("arg")
            self.notebook.select(self.mergeTarget)
        except Exception as e:
            tkinter.messagebox.showinfo("Syntax Error", "Merge syntax is incorrect")

    def RepresentsInt(self, s):
        try:
            int(s)
            return True
        except ValueError:
            return False

    def continueSearch(self, term, rangeValue):
        try:
            direction = self.direction.get()

            tabIndex = self.notebook.index(self.notebook.select())

            self.regexIndex = self.regex.get()
            self.regexOrNot = False

            if self.regexIndex == 1:
                self.regexOrNot = True

            self.hex = self.highlightLineEntry.get()
            self.validHex = re.search(
                r'^#(?:[0-9a-fA-F]{3}){1,2}$', self.highlightLineEntry.get())

            if self.validHex:
                self.standardColor = self.highlightLineEntry.get()
            else:
                self.standardColor = "#66FF66"

            self.matchCaseIndex = self.matchcase.get()
            self.matchCaseOrNot = False

            if self.matchCaseIndex == 1:
                self.matchCaseOrNot = True

            if self.regexOrNot == False:
                if self.matchCaseOrNot:
                    numberOfInstances = self.tabs[tabIndex].text.get(
                        0.0, tk.END).upper().count(term.upper())
                else:
                    numberOfInstances = self.tabs[tabIndex].text.get(
                        0.0, tk.END).upper().count(term.upper())
            else:
                numberOfInstances = len(re.findall(
                    term, self.tabs[tabIndex].getContent()))

            if self.RepresentsInt(self.rangeEntry.get()) and int(self.rangeEntry.get()) <= numberOfInstances and int(self.rangeEntry.get()) > 0:
                self.range = int(self.rangeEntry.get())
            else:
                self.range = numberOfInstances

            if (term != self.previousSearch or direction != self.previousDirection or self.range != self.previousRange or self.matchCaseOrNot != self.previousCaseOrNot or
                    self.regexOrNot != self.previousRegex):
                tabIndex = self.notebook.index(self.notebook.select())
                self.instance = 0
                self.tabs[tabIndex].clearAll("#FFFFFF")

            if len(term) > 0:
                self.instance += 1

                if numberOfInstances > 0:
                    if self.instance == 1 and self.instance <= self.range:
                        if self.regexOrNot == False:
                            if direction == 0 or direction == 1:
                                self.pos = self.tabs[tabIndex].text.search(
                                    term, '1.0', nocase=(not self.matchCaseOrNot))
                                self.finalPos = '{}+{}c'.format(
                                    self.pos, len(term))
                                self.tabs[tabIndex].individualHighlight(
                                    self.pos, self.finalPos, self.standardColor)
                                self.tabs[tabIndex].text.see(self.pos)
                            else:
                                self.pos = self.tabs[tabIndex].text.search(
                                    term, '1.0', backwards=True, nocase=(not self.matchCaseOrNot))
                                self.finalPos = '{}+{}c'.format(
                                    self.pos, len(term))
                                self.tabs[tabIndex].individualHighlight(
                                    self.pos, self.finalPos, self.standardColor)
                                self.finalPos = '{}-{}c'.format(
                                    self.pos, len(term))
                                self.tabs[tabIndex].text.see(self.pos)
                        else:
                            if direction == 0 or direction == 1:
                                self.pos = self.tabs[tabIndex].text.search(
                                    term, '1.0', regexp=True, nocase=(not self.matchCaseOrNot))
                                self.finalPos = '{}+{}c'.format(self.pos, len(
                                    re.search(term, self.tabs[tabIndex].getContent()).group(0)))
                                self.tabs[tabIndex].individualHighlight(
                                    self.pos, self.finalPos, self.standardColor)
                                self.tabs[tabIndex].text.see(self.pos)
                            else:
                                self.pos = self.tabs[tabIndex].text.search(
                                    term, '1.0', regexp=True, backwards=True, nocase=(not self.matchCaseOrNot))
                                self.finalPos = '{}+{}c'.format(self.pos, len(
                                    re.search(term, self.tabs[tabIndex].getContent()).group(0)))
                                self.tabs[tabIndex].individualHighlight(
                                    self.pos, self.finalPos, self.standardColor)
                                self.finalPos = '{}-{}c'.format(self.pos, len(
                                    re.search(term, self.tabs[tabIndex].getContent()).group(0)))
                                self.tabs[tabIndex].text.see(self.pos)

                    elif self.instance <= numberOfInstances:
                        self.previousPos = self.pos
                        self.previousFinalPos = self.finalPos

                        self.pos = self.finalPos

                        if direction == 2:
                            self.tabs[tabIndex].clearPreviousHighlight(self.previousPos, self.previousFinalPos.split(
                                "-")[0] + "+" + self.previousFinalPos.split("-")[1], self.highlightColor)
                        else:
                            self.tabs[tabIndex].clearPreviousHighlight(
                                self.previousPos, self.previousFinalPos, self.highlightColor)

                        if self.regexOrNot == False:
                            if direction == 0 or direction == 1:
                                self.pos = self.tabs[tabIndex].text.search(
                                    term, self.pos, nocase=(not self.matchCaseOrNot))
                                self.finalPos = '{}+{}c'.format(
                                    self.pos, len(term))
                                self.tabs[tabIndex].individualHighlight(
                                    self.pos, self.finalPos, self.standardColor)
                                self.tabs[tabIndex].text.see(self.pos)
                            else:
                                self.pos = self.tabs[tabIndex].text.search(
                                    term, self.pos, backwards=True, nocase=(not self.matchCaseOrNot))
                                self.finalPos = '{}+{}c'.format(
                                    self.pos, len(term))
                                self.tabs[tabIndex].individualHighlight(
                                    self.pos, self.finalPos, self.standardColor)
                                self.finalPos = '{}-{}c'.format(self.pos, len(
                                    re.search(term, self.tabs[tabIndex].getContent()).group(0)))
                                self.tabs[tabIndex].text.see(self.pos)
                        else:
                            self.pos = self.finalPos
                            if direction == 0 or direction == 1:
                                self.pos = self.tabs[tabIndex].text.search(
                                    term, self.pos, regexp=True, nocase=(not self.matchCaseOrNot))
                                self.finalPos = '{}+{}c'.format(self.pos, len(
                                    re.search(term, self.tabs[tabIndex].getContent()).group(0)))
                                self.tabs[tabIndex].individualHighlight(
                                    self.pos, self.finalPos, self.standardColor)
                                self.tabs[tabIndex].text.see(self.pos)
                            else:
                                self.pos = self.tabs[tabIndex].text.search(
                                    term, self.pos, regexp=True, backwards=True, nocase=(not self.matchCaseOrNot))
                                self.finalPos = '{}+{}c'.format(self.pos, len(
                                    re.search(term, self.tabs[tabIndex].getContent()).group(0)))
                                self.tabs[tabIndex].individualHighlight(
                                    self.pos, self.finalPos, self.standardColor)
                                self.finalPos = '{}-{}c'.format(self.pos, len(
                                    re.search(term, self.tabs[tabIndex].getContent()).group(0)))
                                self.tabs[tabIndex].text.see(self.pos)

                self.previousSearch = term

                self.previousDirection = self.direction.get()

                self.previousRange = self.range

                self.previousCaseOrNot = self.matchCaseOrNot

                self.previousRegex = self.regexOrNot
        except:
            pass

    def newFile(self, arg):
        tabIndex = self.notebook.index(self.notebook.select())

        del self.tabs[tabIndex]
        self.notebook.forget(tabIndex)

        t = Tab(self.notebook, "Untitled Document", self)
        self.tabs.append(t)

        self.file = "Untitled Document"
        self.notebook.tab(tabIndex, text=self.file)

        self.notebook.select(tabIndex)

    def openFile(self, arg):
        try:
            self.fileName = tk.filedialog.askopenfilename()

            with open(self.fileName, 'r') as file:
                self.content = file.read()

            tabIndex = self.notebook.index(self.notebook.select())
            self.tabs[tabIndex].displayFile(self.content)

            locations = self.fileName.split("/")
            self.file = locations[len(locations) - 1]
            self.notebook.tab(tabIndex, text=self.file)

            self.tabs[tabIndex].fileOpened = self.fileName
        except IOError as e:
            pass
        except:
            pass

    def deleteContent(self, file):
        file.seek(0)
        file.truncate()

    def saveFile(self, arg):
        
        tabindex = self.notebook.index(self.notebook.select())
        self.content = self.tabs[tabindex].getContent()

        try:
            with open(self.tabs[tabindex].fileOpened, 'w') as file:
                self.deleteContent(file)
                file.write(self.content)
        except IOError as e:
            pass
        except:
            pass

    def saveAsFile(self, arg):
        
        tabIndex = self.notebook.index(self.notebook.select())
        self.content = self.tabs[tabIndex].getContent()

        try:
            self.fileName = tk.filedialog.asksaveasfilename()
            if self.fileName != None:
                with open(self.fileName, 'w') as file:
                    file.write(self.content)

            locations = self.fileName.split("/")
            self.file = locations[len(locations) - 1]
            self.notebook.tab(tabIndex, text=self.file)

            self.tabs[tabIndex].fileOpened = self.fileName
        except IOError as e:
            pass
        except:
            pass

    def addtab(self, arg):
        t = Tab(self.notebook, "Untitled Document", self)
        self.tabs.append(t)

        self.notebook.select(self.notebook.index("end") - 1)
        self.tabs[self.notebook.index(self.notebook.select())].text.focus_set()
        self.tabs[self.notebook.index(self.notebook.select())].text.configure(font=(self.font, self.fontSize))

    def bottomlabel(self):
        self.positionAndLanguage = tk.Label(
            self, text=" Ln: 1, Col: 0", anchor=tk.W, bg="#E7E7E7", font=("Arial", 9))
        self.positionAndLanguage.pack(fill=tk.X, side=tk.BOTTOM)

    def updateBottomLabel(self, line, column, length, language):
        self.positionAndLanguage[
            "text"] = " Ln: {0}, Col: {1}, Length: {2}".format(line, column, str(length))

    def removetab(self, arg):
        numberOfTabs = self.notebook.index("end")

        if numberOfTabs > 1:
            tabIndex = self.notebook.index(self.notebook.select())
            self.notebook.forget(tabIndex)
            self.tabs[self.notebook.index(self.notebook.select())].text.focus_set()
            del self.tabs[tabIndex]

    def protocol(self, arg2, arg3):
        self.master.protocol(arg2, arg3)

    def close(self, arg):
        try:
            os._exit(0)
        except:
            pass
            
def mainCloseProtocol(root, window, wraptype):
    try:
        with open("resources/openfiles.txt", 'w') as file:
            window.deleteContent(file)
            for i in range(0, len(window.tabs)):
                file.write(window.tabs[i].fileOpened)
                file.write("\n")

        with open("resources/selectedfiles.txt", 'w') as file:
            window.deleteContent(file)
            file.write(str(window.notebook.index(window.notebook.select())))

        with open("resources/tabspace.txt", 'w') as file:
            window.deleteContent(file)
            file.write(str(tabSpace))

        with open("resources/wraptype.txt", 'w') as file:
            window.deleteContent(file)
            file.write(wraptype)
    except OSError:
        tkinter.messagebox.showinfo("User Data", "Cache file for files either corrupted or deleted.")
    except Exception as e:
        tkinter.messagebox.showinfo("Unexpected Error", "An unexpected error occured.")
        
    root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    img = tk.PhotoImage(file='icon.PNG')
    root.tk.call('wm', 'iconphoto', root._w, img)
    root.title("Arshi")
    root.geometry("1024x600")
    window = Arshi(root)
    window.pack(side="top", fill="both", expand=True)
    window.protocol("WM_DELETE_WINDOW", lambda: mainCloseProtocol(root, window, wraptype))
    root.mainloop()
