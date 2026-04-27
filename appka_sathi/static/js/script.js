let videoStream = null;
let capturedImage = null;
let explanationVisible = false;

function startCamera() {
  navigator.mediaDevices.getUserMedia({ video: true })
    .then(stream => {
      videoStream = stream;
      const video = document.getElementById("camera");
      video.srcObject = stream;
      video.style.display = "block";
    })
    .catch(err => {
      alert("⚠ Camera access denied. Continuing without photo.");
      capturedImage = null;
    });
}

function capturePhoto() {
  if (!videoStream) {
    alert("Start camera first");
    return;
  }

  const video = document.getElementById("camera");
  const canvas = document.getElementById("snapshot");
  const img = document.getElementById("patientImg");

  canvas.getContext("2d").drawImage(video, 0, 0, canvas.width, canvas.height);
  capturedImage = canvas.toDataURL("image/png");

  img.src = capturedImage;
  img.style.display = "block";

  videoStream.getTracks().forEach(track => track.stop());
  videoStream = null;
  video.style.display = "none";
}


function toggleExplanation() {
  const el = document.getElementById("explanation");
  explanationVisible = !explanationVisible;
  el.style.display = explanationVisible ? "block" : "none";
}


function analyze() {
  console.log("Assess Risk clicked");

  const symptomIds = [
    "chest_pain",
    "breathlessness",
    "palpitations",
    "cold_sweat",
    "cyanosis",
    "unconscious",
    "seizure",
    "slurred_speech",
    "vision_loss",
    "high_fever",
    "persistent_fever",
    "vomiting",
    "diarrhea",
    "dehydration",
    "dizziness",
    "headache",
    "bleeding",
    "fracture",
    "head_injury",
    "burns",
    "abdominal_pain"
  ];

  const symptoms = symptomIds.filter(id => {
    const el = document.getElementById(id);
    return el && el.checked;
  });

  const data = {
    patient_name: document.getElementById("patient_name").value,
    photo: capturedImage,
    age: document.getElementById("age").value,
    bp: document.getElementById("bp").value,
    symptoms: symptoms,
    consent: document.getElementById("consent").checked
  };

  fetch("/triage", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data)
  })
  .then(res => {
    if (!res.ok) {
      return res.json().then(err => {
        alert(err.error || "Consent required");
        throw new Error("Blocked");
      });
    }
    return res.json();
  })
  .then(data => {

    
    const result = document.getElementById("result");
    result.innerText =
      data.message + "\nAI Risk Probability: " + data.ai_probability;
    result.style.display = "block";

   
    const explainBtn = document.getElementById("explainBtn");
    const explanation = document.getElementById("explanation");
    explanation.innerHTML = "";

    if (data.reasons && data.reasons.length > 0) {
      explainBtn.style.display = "inline";
      data.reasons.forEach(r => {
        const li = document.createElement("li");
        li.innerText = r;
        explanation.appendChild(li);
      });
    } else {
      explainBtn.style.display = "none";
    }


    const qr = document.getElementById("qr");
    if (data.qr_code) {
      qr.src = data.qr_code;
      qr.style.display = "block";
    } else {
      qr.style.display = "none";
    }


    const hospitalSection = document.getElementById("hospitalSection");
    const hospitalList = document.getElementById("hospitalList");
    hospitalList.innerHTML = "";

    if (data.nearby_hospitals && data.nearby_hospitals.length > 0) {
      hospitalSection.style.display = "block";

      data.nearby_hospitals.forEach(h => {
        const li = document.createElement("li");
        li.innerText = `${h.name} — ${h.available_beds} beds (${h.distance_km} km)`;

        const btn = document.createElement("button");
        btn.innerText = "Select";
        btn.onclick = () => {
          fetch("/select-hospital", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              referral_id: data.referral_id,
              hospital_name: h.name
            })
          })
          .then(() => alert("Hospital assigned: " + h.name));
        };

        li.appendChild(btn);
        hospitalList.appendChild(li);
      });
    } else {
      hospitalSection.style.display = "none";
    }
  })
  .catch(err => console.error(err));
}
