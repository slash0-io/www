(function () {
  "use strict";
  var TEMPLATE_URL = "https://slash0-templates.s3.amazonaws.com/slash0-onboard.yaml";
  var PUBLISHER_ACCOUNT = "762528398113";

  var btn = document.getElementById("quick-create");
  if (!btn) return;

  // The calculator hands the computed quota over as ?rules=N. Anything else
  // (a bare visit, a bad value) falls back to 0, which makes the stack skip
  // the quota request rather than file one the account may not need.
  var rules = 0;
  var m = /[?&]rules=(\d{1,4})(?:&|$)/.exec(window.location.search);
  if (m) {
    rules = parseInt(m[1], 10);
    if (!isFinite(rules) || rules < 0) rules = 0;
  }

  if (rules > 0) {
    document.getElementById("rules-value").textContent = rules;
    document.getElementById("rules-note").hidden = false;
  }

  btn.href = "https://console.aws.amazon.com/cloudformation/home#/stacks/create/review" +
    "?templateURL=" + encodeURIComponent(TEMPLATE_URL) +
    "&stackName=slash0-onboard" +
    "&param_PublisherAccountIds=" + PUBLISHER_ACCOUNT +
    "&param_DesiredRulesPerSG=" + rules;
})();
