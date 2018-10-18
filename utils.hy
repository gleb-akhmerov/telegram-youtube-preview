(require [hy.contrib.walk [let]])


(defmacro/g! if-let
  [bindings then-form &optional else-form]
  (let [g!form (nth bindings 0)
        g!tst  (nth bindings 1)]
    `(let [g!temp ~g!tst]
       (if g!temp
         (let [~g!form g!temp]
           ~then-form)
         ~else-form))))


(defmacro if-not-let
  [bindings then-form &optional else-form]
  `(if-let ~bindings ~else-form ~then-form))


(defn map-vals [f d]
  (dfor [k v] (.items d)
        [k (f v)]))
