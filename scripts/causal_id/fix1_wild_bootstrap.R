# Wild cluster bootstrap (MacKinnon-Webb) for the rebuilt-panel reform effect,
# as a small-cluster inference cross-check of the noisy null.
.libPaths(c("C:/Users/Jack0/R/lib", .libPaths()))
suppressMessages({library(fixest); library(fwildclusterboot)})
agg <- read.csv("results/causal_id/ted_panel_for_R.csv")
agg$ym <- agg$ymabs
agg$post <- as.integer(agg$cohort > 0 & agg$ym >= agg$cohort)
m <- feols(sb_rate ~ post | id + ym, data = agg, weights = ~n, cluster = ~id)
cat(sprintf("TWFE post coef = %+.4f pp\n", 100*coef(m)["post"]))
set.seed(7)
b <- boottest(m, param = "post", clustid = "id", B = 9999, type = "rademacher")
cat(sprintf("Wild cluster bootstrap (25 clusters, 9999 reps): p = %.3f, 95%% CI [%+.2f, %+.2f] pp\n",
    b$p_val, 100*b$conf_int[1], 100*b$conf_int[2]))
cat(if (b$p_val > 0.05) "-> not significant: confirms the null\n" else "-> significant\n")
