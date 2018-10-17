(defn cat [patterns]
  (.join "" patterns))

(defn seq [&rest patterns]
  (cat patterns))

(defn group [&rest patterns]
  (.format "(?:{})" (cat patterns)))

(defn named [name- &rest patterns]
  (.format "(?P<{}>{})" name- (cat patterns)))

(defn -maybe-group [patterns]
  (setv [p #* ps] patterns)
  (if ps
    (group p #* ps)
    p))

(defn many [&rest patterns]
  (.format "{}+" (-maybe-group patterns)))

(defn maybe [&rest patterns]
  (.format "{}?" (-maybe-group patterns)))

(defn char-class [chars]
  (.format "[{}]" chars))

(defn ahead [&rest patterns]
  (.format "(?={})" (cat patterns)))

(setv start  "^"
      end    "$"
      digit  r"\d"
      number (many digit))
