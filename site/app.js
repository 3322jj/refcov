/* RefCov demo page. Reads the replay data in data/*.json and fills the replay areas.
 * Every value is written with textContent. Nothing from the data is parsed as HTML.
 */
(function () {
  "use strict";

  var STEP_MS = 220;
  var DICTIONARY_PREFIX = "nyc-bldg-dict/";
  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  var LABELS = {
    "tool-call": "Tool call",
    "file-read": "Direct file read (not counted as a read)",
    "mcp-call": "RefCov call (not a unit read)",
    "write:index.html": "Write index.html",
    "write:answer.md": "Write answer.md",
    "write:edit-plan.md": "Write edit-plan.md",
    "final-report": "Final report"
  };

  var KIRO_NOTES = {
    "inferred": "inferred: the 14 November night first trial and the 15 November 21:23 GIS run both record 3.3.0. The records of this pair do not state a version.",
    "record": "from the run's status file",
    "record-batch-start": "version when the batch started"
  };

  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) {
      node.className = className;
    }
    if (text !== undefined && text !== null) {
      node.textContent = text;
    }
    return node;
  }

  function srText(text) {
    return el("span", "sr", text);
  }

  function loadJson(path) {
    return fetch(path, { cache: "no-cache" }).then(function (response) {
      if (!response.ok) {
        throw new Error(path + " returned " + response.status);
      }
      return response.json();
    });
  }

  function failed(statusNode, error) {
    statusNode.textContent = "The replay data could not be loaded (" + error.message +
      "). Open this page over HTTP or HTTPS, not from a local file.";
  }

  function formatSeconds(value) {
    return value.toFixed(1) + " s";
  }

  function gateText() {
    return document.getElementById("gate-text").textContent;
  }

  function addTerm(list, term, value) {
    list.appendChild(el("dt", null, term));
    list.appendChild(el("dd", null, value));
  }

  function fillMeta(list, data) {
    list.textContent = "";
    addTerm(list, "Run", data.run_folder + " (" + data.id + ")");
    addTerm(list, "Date", data.date);
    addTerm(list, "Model", data.model);
    addTerm(list, "kiro-cli", data.kiro_cli.value + " (" + (KIRO_NOTES[data.kiro_cli.basis] || data.kiro_cli.basis) + ")");
    var total = data.seconds + " s";
    if (data.seconds_reconstructed) {
      total += " (rebuilt from log timestamps)";
    }
    addTerm(list, "Total time", total);
  }

  /* Turns the recorded events into a list of items in order. Consecutive unit reads share one
   * grid of cells; every other event is a row in a step list. Returns the items in document order. */
  function buildReplay(root, events) {
    var items = [];
    var steps = null;
    var cells = null;
    root.textContent = "";
    events.forEach(function (ev) {
      if (ev.kind === "read") {
        if (cells === null) {
          cells = el("ol", "cells dense");
          cells.setAttribute("aria-label", "Units read through MCP, in order");
          root.appendChild(cells);
        }
        steps = null;
        var name = ev.display || ev.unit;
        var cell = el("li", "cell read");
        var mark = el("span", null, "\u2713");
        mark.setAttribute("aria-hidden", "true");
        cell.appendChild(mark);
        cell.appendChild(srText("read: " + name));
        cell.title = name;
        cells.appendChild(cell);
        items.push(cell);
        return;
      }
      cells = null;
      if (steps === null) {
        steps = el("ol", "steps");
        root.appendChild(steps);
      }
      var step = el("li", "step " + ev.kind);
      if (ev.kind === "blocked") {
        step.appendChild(el("span", null, gateText()));
        step.appendChild(el("span", "note", "(gate message, translated)"));
      } else {
        step.textContent = LABELS[ev.label] || ev.label;
      }
      steps.appendChild(step);
      items.push(step);
    });
    return items;
  }

  function hideAll(items) {
    items.forEach(function (item) {
      item.classList.add("pending");
      item.classList.remove("revealed");
    });
  }

  /* One controller per replay. States: idle (not started), playing, paused, done. The single
   * button reads "Replay" when idle or done, "Pause" while playing and "Play" while paused.
   * The label changes, so the button does not expose a pressed state. */
  function makeController(items, button) {
    var timer = null;
    var next = 0;
    var state = "idle";

    function setLabel(text) {
      button.textContent = text;
    }

    function clearTimer() {
      if (timer !== null) {
        window.clearTimeout(timer);
        timer = null;
      }
    }

    function tick() {
      if (state !== "playing") {
        return;
      }
      if (next < items.length) {
        var item = items[next];
        item.classList.remove("pending");
        if (item.classList.contains("blocked")) {
          item.classList.add("revealed");
        }
        next += 1;
        timer = window.setTimeout(tick, STEP_MS);
      } else {
        timer = null;
        state = "done";
        setLabel("Replay");
      }
    }

    function start() {
      clearTimer();
      next = 0;
      hideAll(items);
      state = "playing";
      setLabel("Pause");
      tick();
    }

    button.addEventListener("click", function () {
      if (state === "playing") {
        clearTimer();
        state = "paused";
        setLabel("Play");
      } else if (state === "paused") {
        state = "playing";
        setLabel("Pause");
        tick();
      } else {
        start();
      }
    });

    return start;
  }

  /* Replays start once when the replay area is on screen, and the visitor can pause, resume or
   * replay them with the button. With reduced motion the final state stays visible; the CSS shows
   * a note and hides the button. */
  function inViewport(node) {
    var rect = node.getBoundingClientRect();
    return rect.height > 0 && rect.bottom > 0 && rect.top < window.innerHeight;
  }

  function arrangePlayback(replayRoot, items, button) {
    if (reduceMotion) {
      return;
    }
    var start = makeController(items, button);
    hideAll(items);
    if (inViewport(replayRoot) || !("IntersectionObserver" in window)) {
      start();
      return;
    }
    var observer = new IntersectionObserver(function (entries) {
      var visible = entries.some(function (entry) {
        return entry.isIntersecting;
      });
      if (visible) {
        observer.disconnect();
        start();
      }
    }, { threshold: 0.25 });
    observer.observe(replayRoot);
  }

  function loadRun(key, file) {
    var meta = document.getElementById(key + "-meta");
    var status = document.getElementById(key + "-status");
    var button = document.getElementById(key + "-button");
    var root = document.getElementById(key + "-replay");
    loadJson("data/" + file).then(function (data) {
      fillMeta(meta, data);
      var items = buildReplay(root, data.events);
      status.textContent = "";
      arrangePlayback(root, items, button);
    }).catch(function (error) {
      failed(status, error);
    });
  }

  function loadGate(gatePromise) {
    var meta = document.getElementById("gate-meta");
    var status = document.getElementById("gate-status");
    var button = document.getElementById("gate-button");
    var root = document.getElementById("gate-replay");
    gatePromise.then(function (data) {
      fillMeta(meta, data);
      var items = buildReplay(root, data.events);
      status.textContent = "";
      arrangePlayback(root, items, button);
    }).catch(function (error) {
      failed(status, error);
    });
  }

  function loadShots() {
    var status = document.getElementById("shots-status");
    loadJson("data/vb-01.json").then(function (data) {
      fillMeta(document.getElementById("shots-meta"), data);
      var strip = document.getElementById("strip");
      var last = 0;
      strip.textContent = "";
      data.shots.forEach(function (shot) {
        var item = el("li", shot.read ? "shot read" : "shot");
        item.style.flexGrow = String(Math.max(shot.end - shot.start, 0.01));
        item.appendChild(srText(formatSeconds(shot.start) + " to " + formatSeconds(shot.end) +
          (shot.read ? ": read" : ": not read")));
        strip.appendChild(item);
        last = Math.max(last, shot.end);
      });
      document.getElementById("axis-end").textContent = formatSeconds(last);
      status.textContent = "";
    }).catch(function (error) {
      failed(status, error);
    });
  }

  function fillNames(list, names) {
    list.textContent = "";
    names.forEach(function (name) {
      list.appendChild(el("li", "field", name));
    });
  }

  function loadFields(gatePromise) {
    var status = document.getElementById("fields-status");
    gatePromise.then(function (data) {
      var manifest = [];
      var dictionary = [];
      data.events.forEach(function (ev) {
        if (ev.kind !== "read") {
          return;
        }
        var name = ev.display || ev.unit;
        if (ev.unit.indexOf(DICTIONARY_PREFIX) === 0) {
          dictionary.push(name);
        } else {
          manifest.push(name);
        }
      });
      fillNames(document.getElementById("fields-manifest"), manifest);
      fillNames(document.getElementById("fields-dictionary"), dictionary);
      document.getElementById("fields-manifest-title").textContent =
        "Layer manifest: " + manifest.length + " units";
      document.getElementById("fields-dictionary-title").textContent =
        "NYC building dictionary: " + dictionary.length + " units";
      status.textContent = "";
    }).catch(function (error) {
      failed(status, error);
    });
  }

  function start() {
    var gatePromise = loadJson("data/g-01.json");
    loadRun("w", "w-h-03.json");
    loadRun("wb", "wb-h-03.json");
    loadGate(gatePromise);
    loadShots();
    loadFields(gatePromise);
  }

  start();
})();
