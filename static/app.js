const form = document.querySelector("#notice-form");
const fileInput = document.querySelector("#notice-file");
const textInput = document.querySelector("#notice-text");
const statusLine = document.querySelector("#status");
const candidateList = document.querySelector("#candidate-list");
const resultsEmpty = document.querySelector("#results-empty");
const countBadge = document.querySelector("#result-count");
const calendarList = document.querySelector("#calendar-list");
const calendarEmpty = document.querySelector("#calendar-empty");
const recordButton = document.querySelector("#record-button");
const voiceStatus = document.querySelector("#voice-status");
const template = document.querySelector("#candidate-template");
const STORAGE_KEY = "notice2next-demo-calendar";
let voiceConfig = { stt: false, tts: false };
let recorder = null;
let recordingStream = null;
let audioChunks = [];

function setStatus(message, kind = "") {
  statusLine.textContent = message;
  statusLine.className = `status ${kind}`.trim();
}

function safeDate(value) {
  return /^\d{4}-\d{2}-\d{2}$/.test(value || "");
}

function getReminders() {
  try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]"); }
  catch { return []; }
}

function saveReminders(items) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(items));
  renderCalendar();
}

function renderCalendar() {
  const reminders = getReminders().sort((a, b) => a.date.localeCompare(b.date));
  calendarList.replaceChildren();
  calendarEmpty.hidden = reminders.length > 0;
  for (const reminder of reminders) {
    const card = document.createElement("article");
    card.className = "calendar-item";
    const title = document.createElement("strong");
    title.textContent = reminder.title;
    const time = document.createElement("time");
    time.dateTime = reminder.date;
    time.textContent = new Date(`${reminder.date}T12:00:00`).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
    const evidence = document.createElement("p");
    evidence.textContent = `Source page ${reminder.page}: ${reminder.evidence}`;
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "remove-reminder";
    remove.textContent = "Remove";
    remove.addEventListener("click", () => saveReminders(getReminders().filter(item => item.id !== reminder.id)));
    card.append(title, time, evidence, remove);
    calendarList.append(card);
  }
}

function makeCandidate(candidate) {
  const node = template.content.firstElementChild.cloneNode(true);
  node.querySelector(".candidate-kind").textContent = candidate.kind || "date mention";
  node.querySelector(".candidate-page").textContent = `Page ${candidate.page}`;
  const titleInput = node.querySelector(".candidate-title");
  const dateInput = node.querySelector(".candidate-date");
  const evidence = node.querySelector(".evidence");
  titleInput.value = candidate.title || "Review notice";
  dateInput.value = candidate.date_iso || "";
  evidence.textContent = `“${candidate.evidence}”`;

  node.querySelector(".approve-button").addEventListener("click", () => {
    const title = titleInput.value.trim();
    const date = dateInput.value;
    if (!title || !safeDate(date)) {
      setStatus("Add a reminder title and choose a valid date before approving.", "error");
      return;
    }
    const reminders = getReminders();
    reminders.push({
      id: `${candidate.id}-${Date.now()}`,
      title,
      date,
      page: candidate.page,
      evidence: candidate.evidence,
    });
    saveReminders(reminders);
    setStatus("Reminder approved and added to this browser’s demo calendar.", "success");
  });

  node.querySelector(".read-button").addEventListener("click", () => readText(`${titleInput.value}. Source page ${candidate.page}. ${candidate.evidence}`));
  return node;
}

function renderCandidates(data) {
  candidateList.replaceChildren();
  const candidates = data.candidates || [];
  countBadge.textContent = `${candidates.length} found`;
  resultsEmpty.hidden = candidates.length > 0;
  if (!candidates.length) {
    resultsEmpty.textContent = data.message || "No date suggestions found.";
    return;
  }
  resultsEmpty.textContent = "Date suggestions appear here with the page and source sentence that supports them.";
  for (const candidate of candidates) candidateList.append(makeCandidate(candidate));
}

form.addEventListener("submit", async event => {
  event.preventDefault();
  const file = fileInput.files[0];
  const pastedText = textInput.value.trim();
  if (!file && !pastedText) {
    setStatus("Choose a PDF/text file or paste a notice first.", "error");
    return;
  }
  setStatus("Reading the notice…");
  document.querySelector("#analyze-button").disabled = true;
  try {
    let response;
    if (file) {
      const data = new FormData();
      data.append("file", file);
      response = await fetch("/api/analyze", { method: "POST", body: data });
    } else {
      response = await fetch("/api/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: pastedText }),
      });
    }
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Could not read that notice.");
    renderCandidates(result);
    setStatus(result.message || `Read ${result.filename}. Review the source before approving anything.`, "success");
  } catch (error) {
    setStatus(error.message || "Something went wrong while reading the notice.", "error");
  } finally {
    document.querySelector("#analyze-button").disabled = false;
  }
});

document.querySelector("#sample-button").addEventListener("click", async () => {
  try {
    const response = await fetch("/sample_notice.txt");
    textInput.value = await response.text();
    fileInput.value = "";
    setStatus("Fictional sample loaded. Select Find dates and actions to preview it.", "success");
  } catch {
    setStatus("Could not load the sample notice.", "error");
  }
});

document.querySelector("#clear-button").addEventListener("click", () => {
  fileInput.value = "";
  textInput.value = "";
  candidateList.replaceChildren();
  countBadge.textContent = "0 found";
  resultsEmpty.hidden = false;
  resultsEmpty.textContent = "Date suggestions appear here with the page and source sentence that supports them.";
  setStatus("Notice cleared. Nothing was saved.");
});

document.querySelector("#clear-calendar").addEventListener("click", () => {
  saveReminders([]);
  setStatus("The browser’s demo calendar is clear.", "success");
});

async function readText(text) {
  if (voiceConfig.tts && confirm("Send this notice excerpt to ElevenLabs to read it aloud?")) {
    try {
      const response = await fetch("/api/voice/speak", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });
      if (!response.ok) {
        const result = await response.json();
        throw new Error(result.error || "ElevenLabs speech failed.");
      }
      const audio = new Audio(URL.createObjectURL(await response.blob()));
      await audio.play();
      return;
    } catch (error) {
      setStatus(error.message || "Could not play the audio.", "error");
      return;
    }
  }
  if ("speechSynthesis" in window) {
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(new SpeechSynthesisUtterance(text));
  } else {
    setStatus("Text-to-speech is unavailable in this browser.", "error");
  }
}

function stopRecording() {
  if (recorder && recorder.state !== "inactive") recorder.stop();
  recordButton.textContent = "Record question";
}

recordButton.addEventListener("click", async () => {
  if (!voiceConfig.stt) return;
  if (recorder && recorder.state === "recording") {
    stopRecording();
    return;
  }
  if (!confirm("Send your short recording to ElevenLabs for transcription?")) return;
  try {
    recordingStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    audioChunks = [];
    recorder = new MediaRecorder(recordingStream);
    recorder.ondataavailable = event => { if (event.data.size) audioChunks.push(event.data); };
    recorder.onstop = async () => {
      recordingStream?.getTracks().forEach(track => track.stop());
      const blob = new Blob(audioChunks, { type: recorder.mimeType || "audio/webm" });
      const data = new FormData();
      data.append("audio", blob, "question.webm");
      setStatus("Sending audio to ElevenLabs for transcription…");
      try {
        const response = await fetch("/api/voice/transcribe", { method: "POST", body: data });
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || "Transcription failed.");
        textInput.value = result.text;
        setStatus("Transcript added to the notice text box. Review it before analysis.", "success");
      } catch (error) {
        setStatus(error.message || "Could not transcribe that recording.", "error");
      }
    };
    recorder.start();
    recordButton.textContent = "Stop recording";
    setStatus("Recording. Click Stop recording when you finish.");
  } catch (error) {
    setStatus(error.message || "Microphone permission was not available.", "error");
  }
});

async function loadHealth() {
  try {
    const response = await fetch("/api/health");
    const result = await response.json();
    voiceConfig = { stt: result.elevenlabs_stt, tts: result.elevenlabs_tts };
    recordButton.disabled = !voiceConfig.stt;
    voiceStatus.textContent = voiceConfig.stt
      ? "ElevenLabs transcription is ready. Confirm before each recording is sent."
      : "Add ELEVENLABS_API_KEY to .env to enable spoken questions.";
  } catch {
    voiceStatus.textContent = "Voice setup unavailable. Text input still works.";
  }
}

renderCalendar();
loadHealth();
