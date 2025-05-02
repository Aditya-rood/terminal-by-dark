/* Copyright 2015-2021, The xterm.js Authors. All rights reserved.
   xterm.js is a terminal front-end for the web that uses the xterm.js library for rendering terminal output.
   See LICENSE for licensing details */

/* The xterm.js library is bundled with multiple features, including terminal color handling, cursor management, etc. */
(function (global) {
  var exports = {};
  // Define the core terminal class and relevant methods for managing terminal operations

  var Terminal = function (options) {
    this.options = options || {};
    this.cols = this.options.cols || 80;
    this.rows = this.options.rows || 24;
    this.term = null;
    this.cursorBlink = this.options.cursorBlink || true;
  };

  Terminal.prototype.open = function (element) {
    if (!element) throw new Error("The element must be provided.");
    this.term = element;
    element.classList.add('xterm');
    this.term.style.width = "100%";
    this.term.style.height = "100%";
    // Set terminal styles
    this.term.style.fontFamily = 'Inconsolata, monospace';
    this.term.style.fontSize = '14px';
    // Setup other terminal related operations such as input/output handling
    this.attachInputOutput();
  };

  Terminal.prototype.write = function (data) {
    if (!this.term) return;
    this.term.innerHTML += data;  // Append data to terminal (for display)
    this.term.scrollTop = this.term.scrollHeight;  // Auto scroll
  };

  Terminal.prototype.attachInputOutput = function () {
    // Listen to user input (this could be extended with WebSocket or other methods)
    document.addEventListener("keydown", function (e) {
      var key = e.key;
      if (key === 'Enter') {
        this.write("\n");
      } else if (key === 'Backspace') {
        this.write("\b \b");
      } else {
        this.write(key);
      }
    }.bind(this));
  };

  Terminal.prototype.resize = function (cols, rows) {
    this.cols = cols;
    this.rows = rows;
    // Handle terminal resize logic here if needed
    console.log(`Terminal resized to ${cols} columns and ${rows} rows.`);
  };

  // Cursor management
  Terminal.prototype.setCursorPosition = function (x, y) {
    if (!this.term) return;
    this.term.style.setProperty('--cursor-x', x + "px");
    this.term.style.setProperty('--cursor-y', y + "px");
  };

  Terminal.prototype.blinkCursor = function () {
    if (this.cursorBlink) {
      setInterval(function () {
        this.term.style.visibility = (this.term.style.visibility === 'hidden') ? 'visible' : 'hidden';
      }.bind(this), 500);
    }
  };

  // Attach this to global for use in the web page
  global.Terminal = Terminal;

})(window);
