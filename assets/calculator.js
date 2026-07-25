(function () {
  "use strict";
  var FEED = "https://feed.slash0.io/v1/";
  var TEMPLATE_URL = "https://slash0-templates.s3.amazonaws.com/egress-onboard.yaml";
  var PUBLISHER_ACCOUNT = "762528398113";
  // Mirrors the publisher's viability policy: firewall-scale purposes are
  // not deliverable as referenced prefix lists, and neither is anything
  // over the per-family cap.
  var EXCLUDED = {
    "aws/all": true, "azure/all": true, "azure/sql": true,
    "databricks/all": true, "github/actions": true, "okta/all": true
  };
  var FAMILY_CAP = 250;
  var OWN_RULES_ALLOWANCE = 20;
  var DEFAULT_QUOTA = 60;

  // Mirrors the publisher's max_entries sizing: count plus headroom of
  // max(5, 20%), rounded up to a multiple of ten, capped at the AWS max.
  function sizeFor(n) {
    if (n === 0) return 0;
    var headroom = Math.max(5, Math.ceil(n / 5));
    return Math.min(Math.ceil((n + headroom) / 10) * 10, 1000);
  }

  var picker = document.getElementById("picker");
  if (!picker) return;

  fetch(FEED + "index.json").then(function (r) {
    if (!r.ok) throw new Error("index.json: " + r.status);
    return r.json();
  }).then(function (index) {
    picker.textContent = "";
    var boxes = [];

    index.services.forEach(function (s) {
      var group = document.createElement("div");
      group.className = "svc-group";
      var title = document.createElement("h3");
      title.textContent = s.name;
      group.appendChild(title);

      s.purposes.forEach(function (p) {
        var key = s.slug + "/" + p.key;
        var over = Math.max(p.ipv4Count, p.ipv6Count) > FAMILY_CAP;
        var blocked = EXCLUDED[key] || over;

        var row = document.createElement("label");
        row.className = "p-row" + (blocked ? " blocked" : "");
        var box = document.createElement("input");
        box.type = "checkbox";
        box.disabled = blocked;
        box.dataset.v4 = p.ipv4Count;
        box.dataset.v6 = p.ipv6Count;
        row.appendChild(box);
        var code = document.createElement("code");
        code.textContent = key;
        row.appendChild(code);
        var meta = document.createElement("span");
        meta.className = "p-meta";
        if (blocked) {
          meta.textContent = (p.ipv4Count + p.ipv6Count) +
            " ranges; firewall-scale, not deliverable as a referenced prefix list";
        } else {
          var parts = [];
          if (p.ipv4Count) parts.push(p.ipv4Count + " IPv4 (list of " + sizeFor(p.ipv4Count) + ")");
          if (p.ipv6Count) parts.push(p.ipv6Count + " IPv6 (list of " + sizeFor(p.ipv6Count) + ")");
          meta.textContent = p.direction + " · " + parts.join(" · ");
          boxes.push(box);
          box.addEventListener("change", recompute);
        }
        row.appendChild(meta);
        group.appendChild(row);
      });
      picker.appendChild(group);
    });

    function recompute() {
      var lists = 0, v4 = 0, v6 = 0;
      boxes.forEach(function (b) {
        if (!b.checked) return;
        var c4 = +b.dataset.v4, c6 = +b.dataset.v6;
        if (c4) { lists++; v4 += sizeFor(c4); }
        if (c6) { lists++; v6 += sizeFor(c6); }
      });
      var need = Math.max(v4, v6) + (lists ? OWN_RULES_ALLOWANCE : 0);
      var quota = need > DEFAULT_QUOTA ? Math.min(Math.ceil(need / 10) * 10, 1000) : 0;

      document.getElementById("sum-lists").textContent = lists;
      document.getElementById("sum-v4").textContent = v4;
      document.getElementById("sum-v6").textContent = v6;
      document.getElementById("sum-quota").textContent = quota || DEFAULT_QUOTA;
      document.getElementById("quota-note").hidden = !(lists && !quota);

      var btn = document.getElementById("quick-create");
      if (lists) {
        btn.removeAttribute("aria-disabled");
        btn.href = "https://console.aws.amazon.com/cloudformation/home#/stacks/create/review" +
          "?templateURL=" + encodeURIComponent(TEMPLATE_URL) +
          "&stackName=egress-onboard" +
          "&param_PublisherAccountIds=" + PUBLISHER_ACCOUNT +
          "&param_DesiredRulesPerSG=" + quota;
      } else {
        btn.setAttribute("aria-disabled", "true");
        btn.href = "#";
      }
    }
    recompute();
  }).catch(function () {
    picker.textContent = "";
    var p = document.createElement("p");
    p.className = "cl-status";
    p.textContent = "Could not load the catalog. The raw counts are at " + FEED + "index.json.";
    picker.appendChild(p);
  });
})();
