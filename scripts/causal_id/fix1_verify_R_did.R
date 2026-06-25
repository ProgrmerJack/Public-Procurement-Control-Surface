# Independent verification of Fix 1 with the GOLD-STANDARD Callaway & Sant'Anna
# R `did` package (att_gt, doubly-robust, not-yet-treated, multiplier-bootstrap
# simultaneous bands) on the raw-TED-rebuilt country x month panel.
.libPaths(c("C:/Users/Jack0/R/lib", .libPaths()))
suppressMessages(library(did))

df <- read.csv("results/causal_id/ted_panel_for_R.csv")
cat("panel:", nrow(df), "rows,", length(unique(df$id)), "countries,",
    length(unique(df$ymabs)), "months\n\n")

run <- function(yname) {
  out <- att_gt(yname = yname, tname = "ymabs", idname = "id", gname = "cohort",
                data = df, control_group = "notyettreated", est_method = "dr",
                weightsname = "n", bstrap = TRUE, cband = TRUE, base_period = "varying",
                allow_unbalanced_panel = TRUE)
  simple <- aggte(out, type = "simple", na.rm = TRUE)
  dyn    <- aggte(out, type = "dynamic", na.rm = TRUE)
  cat("==== ", yname, " (R did, dr, not-yet-treated) ====\n")
  cat(sprintf("  SIMPLE ATT = %+.4f  (SE %.4f)  95%% CI [%+.4f, %+.4f]  -> pp: %+.2f [%+.2f, %+.2f]\n",
              simple$overall.att, simple$overall.se,
              simple$overall.att - 1.96*simple$overall.se,
              simple$overall.att + 1.96*simple$overall.se,
              100*simple$overall.att,
              100*(simple$overall.att - 1.96*simple$overall.se),
              100*(simple$overall.att + 1.96*simple$overall.se)))
  # dynamic: post-period event-time ATTs
  et <- data.frame(e = dyn$egt, att = dyn$att.egt, se = dyn$se.egt)
  post <- et[et$e >= 0 & et$e <= 12, ]
  cat("  post-period event ATT (pp), e=0..12:\n")
  for (i in seq_len(nrow(post)))
    cat(sprintf("    e=%2d: %+.2f pp (SE %.2f)\n", post$e[i], 100*post$att[i], 100*post$se[i]))
  pre <- et[et$e < 0 & et$e >= -12, ]
  cat(sprintf("  pre-period |ATT| mean = %.2f pp, max = %.2f pp (placebo; ~0 if PT holds)\n",
              mean(abs(100*pre$att)), max(abs(100*pre$att))))
  invisible(list(simple = simple, dyn = dyn))
}

r_sb <- run("sb_rate")
cat("\n")
r_c3 <- run("comp3_rate")

# save a compact summary from the already-computed results
s1 <- r_sb$simple; s2 <- r_c3$simple
writeLines(c("R did att_gt verification (raw-TED monthly panel, dr, not-yet-treated)",
  sprintf("sb_rate    SIMPLE ATT pp = %+.2f  SE %.2f  CI [%+.2f, %+.2f]",
          100*s1$overall.att, 100*s1$overall.se,
          100*(s1$overall.att-1.96*s1$overall.se), 100*(s1$overall.att+1.96*s1$overall.se)),
  sprintf("comp3_rate SIMPLE ATT pp = %+.2f  SE %.2f  CI [%+.2f, %+.2f]",
          100*s2$overall.att, 100*s2$overall.se,
          100*(s2$overall.att-1.96*s2$overall.se), 100*(s2$overall.att+1.96*s2$overall.se))),
  "results/causal_id/fix1_R_did_result.txt")
cat("\nSaved -> results/causal_id/fix1_R_did_result.txt\n")
