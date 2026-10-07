// Shows the current attestation public key on /for-advocates.html (P3-H3).
(function () {
  "use strict";
  const id = document.getElementById("adv-key-id");
  const pub = document.getElementById("adv-key-public");
  const note = document.getElementById("adv-key-note");
  if (!id) return;
  fetch("/api/evidence/attestation-key")
    .then((r) => r.json())
    .then((k) => {
      if (!k.enabled) {
        id.textContent = "Not published";
        note.textContent = "This site is not signing exports at the moment; exports made now carry no attestations.";
        return;
      }
      id.textContent = k.key_id;
      pub.textContent = k.public_key;
      note.textContent = "Signed message format: " + k.message_format;
    })
    .catch(() => { id.textContent = "Unavailable right now"; });
})();
