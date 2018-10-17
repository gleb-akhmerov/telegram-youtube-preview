(require [hy.contrib.walk [let]]
         [utils [if-let if-not-let]])
(import re
        [collections [namedtuple]]
        [utils [map-vals]])


(setv Timestamp (namedtuple "Timestamp" "h m s")
      (. Timestamp --repr--) (fn [s]
                               (.format "Timestamp('{}h{}m{}s')" s.h s.m s.s)))


(defn str-to-ts [s]
  (if-let [m (re.match (+ "^" hms-pattern "$") s)]
    (Timestamp #** (map-vals int (.groupdict m :default 0)))
    (raise ValueError)))


(defn colons-to-ts [s]
  (if-let [m (re.match (+ "^" colons-pattern "$") s)]
    (Timestamp #** (map-vals int (.groupdict m :default 0)))
    (raise ValueError)))


(defn match-to-ts [m]
  (Timestamp #** (map-vals int (.groupdict m :default 0))))


(defn ts-to-seconds [ts]
  (+ (* ts.h 60 60)
     (* ts.m 60)
     ts.s))


(setv hms-pattern
      (+ r"(?=\d+[hms])" ;; require at least one group
         r"(?:(?P<h>\d+)h)?"
         r"(?:(?P<m>\d+)m)?"
         r"(?:(?P<s>\d+)s)?"))


(setv colons-pattern
      (+ r"(?:(?P<h>\d+):)?"
         r"(?P<m>\d+)?:"
         r"(?P<s>\d+)"))


(defn parse-end [end]
  (or
    (try ["length" (Timestamp 0 0 (int end))]
      (except [ValueError]))

    (if-let [m (re.match (+ r"\+" hms-pattern "$") end)]
      ["length" (match-to-ts m)])
    
    (if-let [m (re.match (+ "^" hms-pattern "$") end)]
      ["end" (match-to-ts m)])

    (if-let [m (re.match (+ r"\.\." hms-pattern "$") end)]
      ["ellipsis-end" (match-to-ts m)])

    (raise (ValueError ["don't know how to parse" end]))))


(do
  (assert (= (parse-end "10") ["length" (Timestamp 0 0 10)]))
  (assert (= (parse-end "+1m") ["length" (Timestamp 0 1 0)]))
  (assert (= (parse-end "1h2m3s") ["end" (Timestamp 1 2 3)]))
  (assert (= (parse-end "..1h") ["ellipsis-end" (Timestamp 1 0 0)])))


;; possible combinations
#_(do
    "1h"
    "1m"
    "1s"
    "1h1m"
    "1h1s"
    "1m1s"
    "1h1m1s")


(defn merge-ellipsis [s e]
  (cond [(pos? e.m) (Timestamp s.h e.m e.s)]
        [(pos? e.s) (Timestamp s.h s.m e.s)]
        [True (raise ValueError)]))


#_(merge-ellipsis (str-to-ts "1h2m3s")
                (str-to-ts "5m"))


(defn +ts [a b]
  (Timestamp (+ a.h b.h)
             (+ a.m b.m)
             (+ a.s b.s)))


(defn parse-interval [start end]
  (if-not-let [m (re.match (+ "^" hms-pattern "$") start)]
    (raise (ValueError ["not a valid HMS-pattern" start]))
    (let [s (match-to-ts m)]
      (setv [kind e] (parse-end end))
      (cond [(= kind "ellipsis-end")
             [s (merge-ellipsis s e)]]

            [(= kind "end")
             [s e]]

            [(= kind "length")
             [s (+ts s e)]]))))

#_(do
  (parse-interval "1h2m" "10")
  (parse-interval "1h2m" "1h3m")
  (parse-interval "1h2m" "+3m")
  (parse-interval "1h2s" "..5m"))
