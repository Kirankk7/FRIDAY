// Known-positive fixture for the endpoint/path extractor.
// Mixes the shapes that have actually defeated our extractors on real hunts.
const a = "/api/v1/fixture/plain";                       // plain quoted path
const b = `${base}/api/v1/fixture/template/${id}`;       // template literal (main.js 1MB had ONLY these)
const c = '/fixture/single-quoted';                      // single quotes
const d = "/fixture/with-dash_and.dot/seg";              // punctuation
const e = {url: "/fixture/in-object-value"};             // object value
const f = "/assets/scripts/apps/fixture-app/nl/main.js"; // asset-shaped (must NOT be an endpoint)
const g = "/fixture/image.png";                          // static (must NOT be an endpoint)
fetch("/api/v1/fixture/in-fetch-call");
