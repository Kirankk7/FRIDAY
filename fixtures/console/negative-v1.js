// NEGATIVE FIXTURE - must FAIL the contract. If this ever passes, the
// validator has stopped validating (pb0767 applied to the validator itself).
(async () => {
  const r = await fetch("https://example.com/api/thing", {method:"DELETE"});
  console.log("gated:", r.status === 403 ? "*** ENFORCED ***" : "no");
})();
