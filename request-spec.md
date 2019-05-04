# `request`
is a string of one of the following forms:
- `youtube-url-with-hms` `space` `end`
- `youtube-url` `space` `start` `space` `end`


## `space`
is one or more " " characters.


## `youtube-url`
is a URL, which has:
- protocol — either "http" or "https"
- hostname — either "www.youtube.com" or "youtube.com" or "youtu.be"
- video id, which must be:
  - the first segment of path, if hostname is "youtu.be"
  - the "v" query parameter, otherwise


## `youtube-url-with-hms`
is a `youtube-url` which has the "t" query parameter which is a `hms`.


## `start`
is an absolute timestamp in the form of either a `hms`, a `colons` or a `number`.


## `end`
is one of the following:
- an absolute timestamp in the form of a `hms` or a `colons`
- a relative `number` timestamp — number of seconds
- a relative "+" `hms` timestamp
- a partial relative ".." `hms` timestamp


## `hms`
is a string consisting of three ordered optional parts (at least one must be present) of the form: (`number` "h") (`number` "m") (`number` "s").


## `colons`
is a string of one of the following forms:
- mm:ss
- hh:mm:ss

hh, mm and ss are `number`s.


## `number`
is one or more digits (0-9).
