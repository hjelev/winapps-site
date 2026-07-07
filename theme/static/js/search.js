/* Client-side search over tipuesearch_content.json (replaces Tipue/jQuery). */
(function () {
  var container = document.getElementById("tipue_search_content");
  if (!container) return;

  var root = container.getAttribute("data-root") || "/";
  var query = new URLSearchParams(window.location.search).get("q") || "";
  query = query.trim();

  var input = document.getElementById("tipue_search_input");
  if (input) input.value = query;

  function esc(text) {
    return text.replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }

  function tokenize(text) {
    return text
      .toLowerCase()
      .split(/[^a-z0-9+#]+/)
      .filter(function (t) {
        return t.length >= 2;
      });
  }

  function render(message, resultsHtml) {
    container.innerHTML =
      '<p class="search-summary">' + message + "</p>" + (resultsHtml || "");
  }

  if (!query) {
    render("Type something in the search box above to find an app.");
    return;
  }

  var tokens = tokenize(query);
  var phrase = query.toLowerCase();

  fetch(root + "tipuesearch_content.json")
    .then(function (response) {
      if (!response.ok) throw new Error("index unavailable");
      return response.json();
    })
    .then(function (data) {
      var results = [];
      data.pages.forEach(function (page) {
        var title = page.title.toLowerCase();
        var text = page.text.toLowerCase();
        var tags = (page.tags || "").toLowerCase();
        var score = 0;
        tokens.forEach(function (token) {
          if (title.indexOf(token) !== -1) score += 10;
          if (tags.indexOf(token) !== -1) score += 5;
          if (text.indexOf(token) !== -1) score += 1;
        });
        if (title.indexOf(phrase) !== -1) score += 20;
        if (score > 0) results.push({ page: page, score: score });
      });
      results.sort(function (a, b) {
        return b.score - a.score;
      });

      if (!results.length) {
        render(
          "No apps found for “" + esc(query) +
            "”. Try a shorter keyword or browse the categories above."
        );
        return;
      }

      var html = '<div class="app-list">';
      results.forEach(function (result) {
        var page = result.page;
        var lowerText = page.text.toLowerCase();
        var hit = -1;
        for (var i = 0; i < tokens.length && hit === -1; i++) {
          hit = lowerText.indexOf(tokens[i]);
        }
        var start = Math.max(0, hit - 60);
        var snippet =
          (start > 0 ? "…" : "") +
          page.text.slice(start, start + 200) +
          (start + 200 < page.text.length ? "…" : "");
        snippet = esc(snippet).replace(
          new RegExp(
            "(" +
              tokens
                .map(function (t) {
                  return t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
                })
                .join("|") +
              ")",
            "gi"
          ),
          "<mark>$1</mark>"
        );
        html +=
          '<article class="app-row search-result">' +
          '<div class="app-row-body">' +
          '<h2 class="app-row-title"><a href="' + root + esc(page.url) + '">' +
          esc(page.title) + "</a></h2>" +
          '<p class="app-row-meta"><span class="badge">' + esc(page.tags || "") +
          "</span></p>" +
          '<div class="app-row-summary search-result-snippet">' + snippet +
          "</div></div></article>";
      });
      html += "</div>";

      render(
        results.length +
          (results.length === 1 ? " app found" : " apps found") +
          " for “" + esc(query) + "”",
        html
      );
    })
    .catch(function () {
      render("Search is unavailable right now. Please try again later.");
    });
})();
