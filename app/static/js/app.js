/**
 * Samvaadhika — shared JS utilities
 * Loaded on every page via base.html
 */

// ── Auto-dismiss alerts after 5 seconds ──
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.alert').forEach(el => {
    setTimeout(() => {
      el.style.transition = 'opacity 0.5s';
      el.style.opacity = '0';
      setTimeout(() => el.remove(), 500);
    }, 5000);
  });

  initProductTour();
});

// ── First-visit product tour ──
function initProductTour() {
  const overlay = document.getElementById('tourOverlay');
  const launchButton = document.getElementById('startTourBtn');
  if (!overlay || !launchButton) return;

  const popover = document.getElementById('tourPopover');
  const title = document.getElementById('tourTitle');
  const description = document.getElementById('tourDescription');
  const progress = document.getElementById('tourProgress');
  const languageLabel = document.getElementById('tourLanguageLabel');
  const languageSelect = document.getElementById('tourLanguage');
  const backButton = document.getElementById('tourBackBtn');
  const nextButton = document.getElementById('tourNextBtn');
  const skipButton = document.getElementById('tourSkipBtn');
  const tourContent = {
    en: {
      languageLabel: 'Tour language', progress: 'Step', skip: 'Skip tour', back: 'Back', next: 'Next', done: 'Done',
      steps: [
        ['Your translation workspace', 'Return to the dashboard from anywhere by selecting the Samvaadhika logo.'],
        ['Translate a file', 'Drop a document, spreadsheet, presentation, PDF, audio, or video here to begin.'],
        ['Choose languages', 'Select the source language, or use Auto-detect, then choose the language you want to translate into.'],
        ['Start translation', 'After choosing a file and languages, select Translate. Your work continues in the background.'],
        ['Translate text directly', 'For short content, switch to text mode and translate by typing or pasting text.'],
        ['Track your work', 'Open Jobs anytime to see progress, review completed translations, and download results.'],
      ],
    },
    hi: {
      languageLabel: 'टूर की भाषा', progress: 'चरण', skip: 'टूर छोड़ें', back: 'पीछे', next: 'आगे', done: 'पूर्ण',
      steps: [
        ['अपने अनुवाद कार्यक्षेत्र से परिचित हों', 'Samvaadhika लोगो चुनकर किसी भी पेज से डैशबोर्ड पर वापस जाएँ।'],
        ['फ़ाइल का अनुवाद करें', 'शुरू करने के लिए दस्तावेज़, स्प्रेडशीट, प्रेज़ेंटेशन, PDF, ऑडियो या वीडियो यहाँ डालें।'],
        ['भाषाएँ चुनें', 'स्रोत भाषा चुनें या Auto-detect का उपयोग करें, फिर अनुवाद की लक्ष्य भाषा चुनें।'],
        ['अनुवाद शुरू करें', 'फ़ाइल और भाषाएँ चुनने के बाद Translate चुनें। आपका काम बैकग्राउंड में जारी रहेगा।'],
        ['सीधे टेक्स्ट का अनुवाद करें', 'छोटी सामग्री के लिए टेक्स्ट मोड में जाकर टेक्स्ट लिखें या पेस्ट करें।'],
        ['अपना काम देखें', 'प्रगति देखने, अनुवादों की समीक्षा करने और परिणाम डाउनलोड करने के लिए Jobs खोलें।'],
      ],
    },
    mr: {
      languageLabel: 'टूरची भाषा', progress: 'पायरी', skip: 'टूर वगळा', back: 'मागे', next: 'पुढे', done: 'पूर्ण',
      steps: [
        ['तुमच्या भाषांतर कार्यक्षेत्राची ओळख', 'Samvaadhika लोगो निवडून कोणत्याही पेजवरून डॅशबोर्डवर परत या.'],
        ['फाइलचे भाषांतर करा', 'सुरुवात करण्यासाठी दस्तऐवज, स्प्रेडशीट, प्रेझेंटेशन, PDF, ऑडिओ किंवा व्हिडिओ येथे टाका.'],
        ['भाषा निवडा', 'स्रोत भाषा निवडा किंवा Auto-detect वापरा, त्यानंतर ज्या भाषेत भाषांतर हवे ती भाषा निवडा.'],
        ['भाषांतर सुरू करा', 'फाइल आणि भाषा निवडल्यानंतर Translate निवडा. तुमचे काम बॅकग्राउंडमध्ये सुरू राहील.'],
        ['थेट मजकुराचे भाषांतर करा', 'लहान मजकुरासाठी टेक्स्ट मोडमध्ये जाऊन मजकूर टाइप किंवा पेस्ट करा.'],
        ['तुमचे काम पाहा', 'प्रगती पाहण्यासाठी, भाषांतरांचे पुनरावलोकन करण्यासाठी आणि निकाल डाउनलोड करण्यासाठी Jobs उघडा.'],
      ],
    },
  };
  const steps = [
    { selector: '.navbar-brand' }, { selector: '#dropZone' }, { selector: '.lang-row' },
    { selector: '#translateBtn' }, { selector: '#textModeBtn' }, { selector: '.navbar-link' },
  ];
  let language = localStorage.getItem('samvaadhika-tour-language') || 'en';
  let currentStep = 0;
  let activeTarget = null;

  function closeTour() {
    overlay.classList.add('hidden');
    overlay.setAttribute('aria-hidden', 'true');
    document.body.classList.remove('tour-active');
    if (activeTarget) activeTarget.classList.remove('tour-highlight');
    activeTarget = null;
    localStorage.setItem('samvaadhika-tour-seen', '1');
  }

  function renderStep() {
    if (activeTarget) activeTarget.classList.remove('tour-highlight');
    let step = steps[currentStep];
    let target = document.querySelector(step.selector);
    while (!target && currentStep < steps.length - 1) {
      currentStep += 1;
      step = steps[currentStep];
      target = document.querySelector(step.selector);
    }
    activeTarget = target;
    if (activeTarget) {
      activeTarget.classList.add('tour-highlight');
      activeTarget.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
    const content = tourContent[language];
    languageLabel.textContent = content.languageLabel;
    languageSelect.setAttribute('aria-label', content.languageLabel);
    title.textContent = content.steps[currentStep][0];
    description.textContent = content.steps[currentStep][1];
    progress.textContent = `${content.progress} ${currentStep + 1} / ${steps.length}`;
    skipButton.textContent = content.skip;
    backButton.textContent = content.back;
    nextButton.textContent = currentStep === steps.length - 1 ? content.done : content.next;
    backButton.disabled = currentStep === 0;
    positionPopover(activeTarget);
  }

  function positionPopover(target) {
    popover.classList.remove('tour-popover-above');
    if (!target) return;
    const rect = target.getBoundingClientRect();
    const popoverHeight = popover.offsetHeight;
    const fitsBelow = rect.bottom + popoverHeight + 20 < window.innerHeight;
    if (!fitsBelow) popover.classList.add('tour-popover-above');
    const left = Math.min(Math.max(16, rect.left + rect.width / 2 - 170), window.innerWidth - 356);
    popover.style.left = `${left}px`;
    popover.style.top = fitsBelow ? `${rect.bottom + 14}px` : `${Math.max(16, rect.top - popoverHeight - 14)}px`;
  }

  function startTour() {
    currentStep = 0;
    overlay.classList.remove('hidden');
    overlay.setAttribute('aria-hidden', 'false');
    document.body.classList.add('tour-active');
    renderStep();
    nextButton.focus();
  }

  launchButton.addEventListener('click', startTour);
  languageSelect.value = language;
  languageSelect.addEventListener('change', () => {
    language = languageSelect.value;
    localStorage.setItem('samvaadhika-tour-language', language);
    renderStep();
  });
  skipButton.addEventListener('click', closeTour);
  backButton.addEventListener('click', () => {
    if (currentStep > 0) { currentStep -= 1; renderStep(); }
  });
  nextButton.addEventListener('click', () => {
    if (currentStep >= steps.length - 1) {
      closeTour();
    } else {
      currentStep += 1;
      renderStep();
    }
  });
  overlay.addEventListener('click', event => {
    if (event.target === overlay) closeTour();
  });
  document.addEventListener('keydown', event => {
    if (overlay.classList.contains('hidden')) return;
    if (event.key === 'Escape') closeTour();
    if (event.key === 'ArrowRight') nextButton.click();
    if (event.key === 'ArrowLeft') backButton.click();
  });
  window.addEventListener('resize', () => {
    if (!overlay.classList.contains('hidden')) positionPopover(activeTarget);
  });

  if (!localStorage.getItem('samvaadhika-tour-seen')) {
    window.setTimeout(startTour, 500);
  }
}

// ── Copy-to-clipboard helper ──
function copyToClipboard(text) {
  navigator.clipboard.writeText(text).then(() => {
    showToastGlobal('Copied to clipboard', 1800);
  });
}

// ── Global toast (used by any page) ──
function showToastGlobal(msg, duration = 3000) {
  let toast = document.getElementById('globalToast');
  if (!toast) {
    toast = document.createElement('div');
    toast.id = 'globalToast';
    toast.style.cssText = `
      position:fixed;bottom:1.5rem;left:50%;transform:translateX(-50%);
      background:var(--green-dark);color:white;
      padding:0.6rem 1.25rem;border-radius:8px;
      font-size:0.85rem;box-shadow:0 4px 16px rgba(0,0,0,0.2);
      z-index:9999;transition:opacity 0.3s;
    `;
    document.body.appendChild(toast);
  }
  toast.textContent = msg;
  toast.style.opacity = '1';
  clearTimeout(toast._timer);
  toast._timer = setTimeout(() => { toast.style.opacity = '0'; }, duration);
}

// ── Confirm-before-delete helper ──
function confirmDelete(message, callback) {
  if (confirm(message || 'Are you sure?')) callback();
}

// ── Format file size ──
function formatBytes(bytes) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / 1048576).toFixed(1) + ' MB';
}

// ── Relative time ──
function relativeTime(isoString) {
  if (!isoString) return '—';
  const diff = Date.now() - new Date(isoString).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}
