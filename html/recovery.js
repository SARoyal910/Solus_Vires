(function () {
  "use strict";

  var PROGRESS_KEY = "sv_recovery_progress";

  var PROGRESS_ITEMS = [
    { id: "stage-safety", label: "Spent time on Safety & stabilization" },
    { id: "stage-mourning", label: "Spent time on Remembrance & mourning" },
    { id: "stage-reconnection", label: "Spent time on Reconnection & growth" },
    { id: "tool-breathing", label: "Tried box breathing" },
    { id: "tool-grounding", label: "Tried 5-4-3-2-1 grounding" },
    { id: "tool-affirmations", label: "Read a grounding reminder" },
    { id: "tool-journal", label: "Opened private Notes" },
  ];

  function loadProgress() {
    try {
      var raw = window.localStorage.getItem(PROGRESS_KEY);
      var parsed = raw ? JSON.parse(raw) : [];
      return Array.isArray(parsed) ? parsed : [];
    } catch (e) {
      return [];
    }
  }

  function saveProgress(ids) {
    try {
      window.localStorage.setItem(PROGRESS_KEY, JSON.stringify(ids));
    } catch (e) {
      // localStorage unavailable (private mode, etc.) - progress just won't persist.
    }
  }

  function markProgress(id) {
    var ids = loadProgress();
    if (ids.indexOf(id) === -1) {
      ids.push(id);
      saveProgress(ids);
      renderProgress();
    }
  }

  function renderProgress() {
    var ids = loadProgress();
    var list = document.getElementById("progress-summary");
    if (list) {
      list.textContent = "";
      if (ids.length === 0) {
        var empty = document.createElement("li");
        empty.textContent = "Nothing logged yet — that's completely fine.";
        empty.style.color = "var(--muted)";
        list.appendChild(empty);
      } else {
        PROGRESS_ITEMS.forEach(function (item) {
          if (ids.indexOf(item.id) !== -1) {
            var li = document.createElement("li");
            li.textContent = item.label;
            list.appendChild(li);
          }
        });
      }
    }

    document.querySelectorAll("[data-progress]").forEach(function (box) {
      box.checked = ids.indexOf(box.getAttribute("data-progress")) !== -1;
    });
  }

  document.querySelectorAll("input[data-progress]").forEach(function (box) {
    box.addEventListener("change", function () {
      if (box.checked) markProgress(box.getAttribute("data-progress"));
    });
  });

  var resetBtn = document.getElementById("progress-reset");
  if (resetBtn) {
    resetBtn.addEventListener("click", function () {
      saveProgress([]);
      renderProgress();
    });
  }

  renderProgress();

  // ---------- Box breathing ----------

  var breathCircle = document.getElementById("breath-circle");
  var breathLabel = document.getElementById("breath-label");
  var breathStatus = document.getElementById("breath-status");
  var breathWrap = document.getElementById("breath-wrap");
  var breathStart = document.getElementById("breath-start");
  var breathStop = document.getElementById("breath-stop");
  var breathTimer = null;
  var breathCycles = 0;

  var BREATH_PHASES = [
    { name: "inhale", label: "Breathe in...", ms: 4000 },
    { name: "hold", label: "Hold", ms: 4000 },
    { name: "exhale", label: "Breathe out...", ms: 4000 },
    { name: "hold", label: "Hold", ms: 4000 },
  ];

  function runBreathPhase(index) {
    var phase = BREATH_PHASES[index % BREATH_PHASES.length];
    breathCircle.className = "breath-circle " + phase.name;
    breathLabel.textContent = phase.label;
    if (phase.name === "inhale" && index > 0) {
      breathCycles += 1;
      breathStatus.textContent = "Cycle " + breathCycles + " · stop any time";
    }
    breathTimer = window.setTimeout(function () {
      runBreathPhase(index + 1);
    }, phase.ms);
  }

  if (breathStart) {
    breathStart.addEventListener("click", function () {
      markProgress("tool-breathing");
      breathWrap.hidden = false;
      breathStart.hidden = true;
      breathStop.hidden = false;
      breathCycles = 0;
      breathStatus.textContent = "";
      runBreathPhase(0);
    });
  }

  if (breathStop) {
    breathStop.addEventListener("click", function () {
      if (breathTimer) window.clearTimeout(breathTimer);
      breathWrap.hidden = true;
      breathStart.hidden = false;
      breathStop.hidden = true;
      breathCircle.className = "breath-circle";
      breathLabel.textContent = "Ready";
    });
  }

  // ---------- 5-4-3-2-1 grounding ----------

  var GROUNDING_STEPS = [
    "Name 5 things you can see around you.",
    "Name 4 things you can touch or feel.",
    "Name 3 things you can hear right now.",
    "Name 2 things you can smell.",
    "Name 1 thing you can taste, or are grateful for.",
  ];

  var groundingWrap = document.getElementById("grounding-wrap");
  var groundingStartActions = document.getElementById("grounding-start-actions");
  var groundingStart = document.getElementById("grounding-start");
  var groundingNext = document.getElementById("grounding-next");
  var groundingRestart = document.getElementById("grounding-restart");
  var groundingPrompt = document.getElementById("grounding-prompt");
  var groundingInput = document.getElementById("grounding-input");
  var groundingStep = 0;

  function showGroundingStep() {
    if (groundingStep >= GROUNDING_STEPS.length) {
      groundingPrompt.textContent = "Nice work. You can restart any time, or come back later.";
      groundingNext.hidden = true;
    } else {
      groundingPrompt.textContent = GROUNDING_STEPS[groundingStep];
      groundingNext.hidden = false;
    }
    groundingInput.value = "";
  }

  if (groundingStart) {
    groundingStart.addEventListener("click", function () {
      markProgress("tool-grounding");
      groundingStartActions.hidden = true;
      groundingWrap.hidden = false;
      groundingStep = 0;
      showGroundingStep();
    });
  }

  if (groundingNext) {
    groundingNext.addEventListener("click", function () {
      groundingStep += 1;
      showGroundingStep();
    });
  }

  if (groundingRestart) {
    groundingRestart.addEventListener("click", function () {
      groundingStep = 0;
      showGroundingStep();
    });
  }

  // ---------- Grounding reminders ----------

  var AFFIRMATIONS = [
    "What happened to you was not your fault.",
    "Healing doesn't follow a straight line, and there's no deadline on it.",
    "You're allowed to feel however you actually feel about this.",
    "Asking for help is a sign of strength, not weakness.",
    "You survived. That took real strength, even if it didn't feel like a choice.",
    "You get to decide what your story means, and when to tell it.",
    "Small steps still count as progress.",
  ];

  var affirmationText = document.getElementById("affirmation-text");
  var affirmationNext = document.getElementById("affirmation-next");
  var affirmationIndex = 0;

  if (affirmationNext) {
    affirmationNext.addEventListener("click", function () {
      markProgress("tool-affirmations");
      affirmationIndex = (affirmationIndex + 1) % AFFIRMATIONS.length;
      affirmationText.textContent = '"' + AFFIRMATIONS[affirmationIndex] + '"';
    });
  }

  // ---------- Notes link ----------

  var journalLink = document.querySelector('[data-progress-id="tool-journal"] a.btn');
  if (journalLink) {
    journalLink.addEventListener("click", function () {
      markProgress("tool-journal");
    });
  }
})();
