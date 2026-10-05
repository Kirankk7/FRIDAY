// POSITIVE FIXTURE - must PASS the contract.
(async () => {
  const H = {"Accept":"application/json"};
  // CONTROL: our own object must come back real, or the batch is unreadable
  const c = await fetch("/api/own-object", {credentials:"include", headers:H});
  console.log("CONTROL own ->", c.status, JSON.stringify((await c.text()).slice(0,200)));
  const t = await fetch("/api/foreign-object", {credentials:"include", headers:H});
  console.log("probe foreign ->", t.status, JSON.stringify((await t.text()).slice(0,200)));
})();
