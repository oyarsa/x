;; vim: ft=racket
(base-cmd "python")
(load-env ".env")
(load-config "config.json")

(types
 (model '("small" "medium" "large"))
 (dataset '("train" "test"))
 (metrics (from-shell "python list_metrics.py")))

(def
 ((model model) (or (env "MODEL") (conf "model") "small"))
 ((dataset dataset) (or (env "DATASET") "test"))
 (root (git-root))
 (timestamp (current-timestamp))
 (debug (if (equal? model "small") "true" "false"))
 (learning-rate (and (equal? model "large") (conf "lr")))
 (outdir "{root}/results/{timestamp}")
 (output "{outdir}/{model}/{dataset}")
 (params "--model {model} --data {dataset} --debug {debug}"))

(task train "Train model"
 (desc "Train model with given parameters")
 (meta
   (owner "ML Team")
   (priority "high"))
 (cmd "train.py {params} --output {output}"))

(group eval "Evaluation tasks"
 (desc "Various model evaluation metrics")
 (params "--model {model} --data {dataset}")
 (cmd "eval.py {params} --metric {metric}")

 (task accuracy "Compute accuracy"
   (desc "Calculate model accuracy with custom threshold")
   (meta (threshold "0.5"))
   (params "{params} --threshold 0.5")
   (metric "accuracy"))

 (task f1 "Compute F1 score"
   (metric "f1")))

(task full "Full pipeline"
 (desc "Run complete training and evaluation pipeline")
 (steps train eval.accuracy eval.f1)
 (shell "echo Done"))

(task default "Show available tasks"
 (shell "dsl --list"))

;; Usage examples:
;; List all tasks:           dsl --list
;; Run with args:           dsl eval.accuracy -- --verbose
;; Run group:               dsl eval
;; Run specific task:       dsl eval.f1
;; Run multiple:            dsl train eval.accuracy
