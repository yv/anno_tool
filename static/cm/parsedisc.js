var RelParser = Editor.Parser = (function() {
	var tokenizeRels = (function() {
		function normal(source, setState) {
		    var ch = source.next();
		    if (ch == "/" && source.equals("/")) {
			setState(inCComment);
			return null;
		    }
		    else if (ch == "(") {
			return "drel-punct";
		    } else if (ch==",") {
			return "drel-punct";
		    } else if (ch==")") {
			return "drel-punct";
		    } else if (ch=="-") {
			return "drel-punct";
		    } else if (/\d/.test(ch) &&
			       source.matches(/[\d\.]/)) {
			source.nextWhileMatches(/[0-9\.]/);
			return "drel-edu";
		    } else if (ch=="T" && source.matches(/[\d]/)) {
			source.nextWhileMatches(/[\d]/);
			return "drel-edu";
		    } else if (/[A-Z]/.test(ch)) {
			source.nextWhileMatches(/[A-Za-z-]/);
			return "drel-rel";
		    } else {
			return "drel-unknown";
		    }
		}
		
		function inCComment(source, setState) {
		    var maybeEnd = false;
		    while (!source.endOfLine()) {
			var ch = source.next();
		    }
		    setState(normal);
		    return "drel-comment";
		}

		return function(source, startState) {
		    return tokenizer(source, startState || normal);
		};
	    })();

	// This is a very simplistic parser -- since CSS does not really
	// nest, it works acceptably well, but some nicer colouroing could
	// be provided with a more complicated parser.
	function parseRels(source, basecolumn) {
	    basecolumn = basecolumn || 0;
	    var tokens = tokenizeRels(source);
	    var inBraces = false, inRule = false, inDecl = false;
	    var iter = {
		next: function() {
		    var tok = tokens.next();
		    if (tok.content == "\n") {
			tok.indentation = function() { return 0; }
		    }
		    return tok;
		},
		copy: function() {
		    return function(_source) {
			source = tokenizeRels(_source,tokens.state);
			return iter;
		    };
		}
	    };
	    return iter;
	}
	
	return {make: parseRels};
    })();

