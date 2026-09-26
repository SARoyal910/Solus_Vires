// "Find help near you" state picker (legal.html, resources.html).
// Links to the state's page on WomensLaw.org. Every code below was checked to
// load a page naming that state on 2026-09-26. Nothing is stored or sent;
// without JavaScript the link falls back to WomensLaw's own state list.
(function () {
  const STATES = [["al", "Alabama"], ["ak", "Alaska"], ["az", "Arizona"], ["ar", "Arkansas"], ["ca", "California"], ["co", "Colorado"], ["ct", "Connecticut"], ["de", "Delaware"], ["dc", "District of Columbia"], ["fl", "Florida"], ["ga", "Georgia"], ["hi", "Hawaii"], ["id", "Idaho"], ["il", "Illinois"], ["in", "Indiana"], ["ia", "Iowa"], ["ks", "Kansas"], ["ky", "Kentucky"], ["la", "Louisiana"], ["me", "Maine"], ["md", "Maryland"], ["ma", "Massachusetts"], ["mi", "Michigan"], ["mn", "Minnesota"], ["ms", "Mississippi"], ["mo", "Missouri"], ["mt", "Montana"], ["ne", "Nebraska"], ["nv", "Nevada"], ["nh", "New Hampshire"], ["nj", "New Jersey"], ["nm", "New Mexico"], ["ny", "New York"], ["nc", "North Carolina"], ["nd", "North Dakota"], ["oh", "Ohio"], ["ok", "Oklahoma"], ["or", "Oregon"], ["pa", "Pennsylvania"], ["pr", "Puerto Rico"], ["ri", "Rhode Island"], ["sc", "South Carolina"], ["sd", "South Dakota"], ["tn", "Tennessee"], ["tx", "Texas"], ["ut", "Utah"], ["vt", "Vermont"], ["va", "Virginia"], ["wa", "Washington"], ["wv", "West Virginia"], ["wi", "Wisconsin"], ["wy", "Wyoming"]];

  document.querySelectorAll("[data-state-finder]").forEach((finder) => {
    const select = finder.querySelector("select");
    const link = finder.querySelector("a[data-womenslaw]");
    if (!select || !link) return;

    for (const [code, name] of STATES) {
      const option = document.createElement("option");
      option.value = code;
      option.textContent = name;
      select.appendChild(option);
    }
    select.hidden = false;

    select.addEventListener("change", () => {
      const chosen = STATES.find(([code]) => code === select.value);
      if (!chosen) {
        link.href = "https://www.womenslaw.org/laws";
        link.textContent = "Choose your state on WomensLaw";
        return;
      }
      link.href = "https://www.womenslaw.org/laws/" + chosen[0];
      link.textContent = chosen[1] + " laws on WomensLaw →";
    });
  });
})();
