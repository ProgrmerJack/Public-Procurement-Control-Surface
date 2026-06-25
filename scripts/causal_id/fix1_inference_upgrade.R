# Fix 1 remainder + inference upgrade on the raw-rebuilt panel:
#  (1) Sun-Abraham IW estimator (fixest::sunab) -- cross-check the aggregate null
#  (2) wild-cluster bootstrap p-value for the aggregate
#  (3) HonestDiD relative-magnitudes breakdown for the HIGH-carbon tercile (the one
#      significant heterogeneity finding)
.libPaths(c("C:/Users/Jack0/R/lib", .libPaths()))
suppressMessages({library(did); library(fixest); library(HonestDiD)})

agg <- read.csv("results/causal_id/ted_panel_for_R.csv")
agg$ym <- agg$ymabs

## (1) Sun-Abraham (no never-treated -> use last cohort implicitly; bin endpoints)
saok <- tryCatch({
  m <- feols(sb_rate ~ sunab(cohort, ym) | id + ym, data = agg, weights = ~n, cluster = ~id)
  att <- summary(m, agg = "att")
  ct <- att$coeftable
  cat(sprintf("(1) Sun-Abraham aggregate ATT = %+.4f (SE %.4f, p %.3f) -> %+.2f pp\n",
      ct[1,1], ct[1,2], ct[1,4], 100*ct[1,1])); TRUE
}, error = function(e) {cat("(1) Sun-Abraham failed:", conditionMessage(e), "\n"); FALSE})

## (2) wild cluster bootstrap on a simple post-treatment indicator TWFE
wbok <- tryCatch({
  agg$post <- as.integer(agg$cohort > 0 & agg$ym >= agg$cohort)
  m2 <- feols(sb_rate ~ post | id + ym, data = agg, weights = ~n, cluster = ~id)
  b <- boottest(m2, param = "post", clustid = "id", B = 9999)
  cat(sprintf("(2) Wild cluster bootstrap (post): coef %+.4f, p = %.3f, 95%% CI [%+.4f, %+.4f]\n",
      coef(m2)["post"], b$p_val, b$conf_int[1], b$conf_int[2])); TRUE
}, error = function(e) {cat("(2) wild bootstrap failed:", conditionMessage(e), "\n"); FALSE})

## (3) HonestDiD on the high-carbon tercile event study
hdok <- tryCatch({
  df <- read.csv("results/causal_id/ted_panel_terc_high.csv")
  out <- att_gt(yname="sb_rate", tname="ym", idname="id", gname="cohort", data=df,
                control_group="notyettreated", est_method="dr", weightsname="n",
                bstrap=TRUE, cband=TRUE, base_period="varying", allow_unbalanced_panel=TRUE)
  es <- aggte(out, type="dynamic", na.rm=TRUE)
  # proper vcov from the influence function (did+HonestDiD vignette approach)
  inf <- es$inf.function$dynamic.inf.func.e
  n <- nrow(inf)
  Vfull <- t(inf) %*% inf / n / n
  ord <- order(es$egt); egt_all <- es$egt[ord]
  beta_all <- es$att.egt[ord]; Vfull <- Vfull[ord, ord]
  keep <- which(egt_all >= -6 & egt_all <= 8)
  betahat <- beta_all[keep]; egt <- egt_all[keep]; sig <- Vfull[keep, keep]
  npre <- sum(egt < 0); npost <- sum(egt >= 0)
  lvec <- rep(1/npost, npost)        # average post-period effect (= the -16 pp ATT)
  cat(sprintf("    (high-carbon averaged post-effect = %+.2f pp)\n", 100*sum(lvec*betahat[egt>=0])))
  hd <- createSensitivityResults_relativeMagnitudes(
        betahat = betahat, sigma = sig, numPrePeriods = npre, numPostPeriods = npost,
        l_vec = lvec, Mbarvec = c(0, 0.5, 1, 1.5, 2))
  cat("(3) HonestDiD (high-carbon tercile, avg post-effect) relative-magnitudes robust CIs (pp):\n")
  hd$lb <- 100*hd$lb; hd$ub <- 100*hd$ub
  print(hd[, c("Mbar","lb","ub")])
  TRUE
}, error = function(e) {cat("(3) HonestDiD failed:", conditionMessage(e), "\n"); FALSE})
