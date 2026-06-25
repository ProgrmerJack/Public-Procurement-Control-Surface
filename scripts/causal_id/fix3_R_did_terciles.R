# Canonical R did ATT per carbon tercile (verify the hand-rolled Fix 3 heterogeneity).
.libPaths(c("C:/Users/Jack0/R/lib", .libPaths()))
suppressMessages(library(did))
for (t in c("low","mid","high")) {
  df <- read.csv(sprintf("results/causal_id/ted_panel_terc_%s.csv", t))
  out <- att_gt(yname="sb_rate", tname="ym", idname="id", gname="cohort", data=df,
                control_group="notyettreated", est_method="dr", weightsname="n",
                bstrap=TRUE, cband=TRUE, base_period="varying", allow_unbalanced_panel=TRUE)
  s <- aggte(out, type="simple", na.rm=TRUE)
  cat(sprintf("%s-carbon: ATT = %+.2f pp  SE %.2f  95%% CI [%+.2f, %+.2f]\n",
      t, 100*s$overall.att, 100*s$overall.se,
      100*(s$overall.att-1.96*s$overall.se), 100*(s$overall.att+1.96*s$overall.se)))
}
