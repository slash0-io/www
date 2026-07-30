(function () {
  "use strict";
  var FEED = "https://feed.slash0.io/v1/";

  function getJSON(path) {
    return fetch(FEED + path).then(function (r) {
      if (!r.ok) throw new Error(path + ": " + r.status);
      return r.json();
    });
  }

  function relTime(iso) {
    var m = Math.floor((Date.now() - new Date(iso).getTime()) / 60000);
    if (m < 1) return "just now";
    if (m < 60) return m + "m ago";
    var h = Math.floor(m / 60);
    if (h < 48) return h + "h ago";
    return Math.floor(h / 24) + "d ago";
  }

  function utcStamp(iso) {
    return iso.slice(0, 10) + " " + iso.slice(11, 16) + " UTC";
  }

  function purposeCount(index) {
    var n = 0;
    index.services.forEach(function (s) { n += (s.purposes || []).length; });
    return n;
  }

  // Landing page: stats strip in the hero. Stays hidden if the feed
  // is unreachable.
  var strip = document.getElementById("live-stats");
  if (strip) {
    Promise.all([getJSON("index.json"), getJSON("changelog.json")])
      .then(function (res) {
        var index = res[0], changelog = res[1];
        document.getElementById("live-services").textContent = index.services.length;
        document.getElementById("live-purposes").textContent = purposeCount(index);
        var changed = document.getElementById("live-changed");
        if (changelog.length) {
          changed.textContent = relTime(changelog[0].publishedAt);
          changed.title = utcStamp(changelog[0].publishedAt);
        } else {
          document.getElementById("live-changed-wrap").hidden = true;
        }
        strip.hidden = false;
      })
      .catch(function () {});
  }

  // Coverage page: how many services fall into each classification. Rendered
  // live so the page can never understate or overstate what is pinnable.
  var cov = document.getElementById("cov-dedicated");
  if (cov) {
    getJSON("index.json")
      .then(function (index) {
        var counts = { dedicated: 0, mixed: 0, "cdn-shared": 0 };
        index.services.forEach(function (s) {
          if (counts[s.classification] !== undefined) counts[s.classification]++;
        });
        document.getElementById("cov-dedicated").textContent = counts.dedicated;
        document.getElementById("cov-mixed").textContent = counts.mixed;
        document.getElementById("cov-cdn").textContent = counts["cdn-shared"];
        document.getElementById("cov-nonpub").textContent =
          (index.nonPublishers || []).length;
      })
      .catch(function () {});
  }

  // Service pages: live ranges, counts, and last-changed per purpose.
  var svc = document.getElementById("service-page");
  if (svc) {
    var slug = svc.getAttribute("data-slug");
    Promise.all([
      getJSON("services/" + slug + ".json"),
      getJSON("changelog.json")
    ]).then(function (res) {
      var doc = res[0], changelog = res[1];
      Object.keys(doc.purposes).forEach(function (key) {
        var p = doc.purposes[key];
        var v4 = p.ipv4 || [], v6 = p.ipv6 || [];
        var pre = document.getElementById("ranges-" + key);
        if (pre) pre.textContent = v4.concat(v6).join("\n");
        var c4 = document.getElementById("count4-" + key);
        if (c4) c4.textContent = v4.length;
        var c6 = document.getElementById("count6-" + key);
        if (c6) c6.textContent = v6.length;
        var quota = document.getElementById("quota-" + key);
        if (quota && v4.length > 60) quota.hidden = false;
      });
      for (var i = 0; i < changelog.length; i++) {
        var hit = changelog[i].changes.some(function (c) { return c.slug === slug; });
        if (hit) {
          var rel = document.getElementById("svc-updated-rel");
          rel.textContent = relTime(changelog[i].publishedAt);
          rel.title = utcStamp(changelog[i].publishedAt);
          document.getElementById("svc-updated").hidden = false;
          break;
        }
      }
    }).catch(function () {
      var pres = svc.querySelectorAll("pre.ranges");
      for (var i = 0; i < pres.length; i++) {
        pres[i].textContent = "Could not load ranges. The raw data is at " +
          FEED + "services/" + slug + ".json";
      }
    });
  }

  // Changelog page: full history, newest first.
  var root = document.getElementById("changelog");
  if (root) {
    var status = document.getElementById("cl-status");
    Promise.all([getJSON("index.json"), getJSON("changelog.json")])
      .then(function (res) {
        var index = res[0], changelog = res[1];
        var names = {};
        index.services.forEach(function (s) { names[s.slug] = s.name; });

        if (!changelog.length) {
          status.textContent = "No range changes recorded yet.";
          return;
        }

        var oldest = changelog[changelog.length - 1].publishedAt;
        status.textContent = changelog.length +
          " publishes have changed service ranges since " +
          oldest.slice(0, 10) + ".";

        changelog.forEach(function (event) {
          var box = document.createElement("div");
          box.className = "cl-event";

          var when = document.createElement("div");
          when.className = "cl-when";
          var abs = document.createElement("span");
          abs.textContent = utcStamp(event.publishedAt);
          var rel = document.createElement("span");
          rel.className = "cl-rel";
          rel.textContent = relTime(event.publishedAt);
          when.appendChild(abs);
          when.appendChild(rel);
          box.appendChild(when);

          event.changes.forEach(function (c) {
            var row = document.createElement("div");
            row.className = "cl-row";
            var code = document.createElement("code");
            code.textContent = c.slug + "/" + c.purpose;
            var name = document.createElement("a");
            name.className = "cl-name";
            name.href = "/services/" + c.slug + "/";
            name.textContent = names[c.slug] || c.slug;
            var delta = document.createElement("span");
            delta.className = "cl-delta";
            if (c.added) {
              var add = document.createElement("b");
              add.className = "add";
              add.textContent = "+" + c.added;
              delta.appendChild(add);
            }
            if (c.removed) {
              var rem = document.createElement("b");
              rem.className = "rem";
              rem.textContent = "−" + c.removed;
              delta.appendChild(rem);
            }
            row.appendChild(code);
            row.appendChild(name);
            row.appendChild(delta);
            box.appendChild(row);
          });

          root.appendChild(box);
        });
      })
      .catch(function () {
        status.textContent = "Could not load the changelog. The raw data is at " +
          FEED + "changelog.json.";
      });
  }
})();
