// taxonomy-based annotation
// requirements:
// * the variable "schema" contains a tree of categories
//   for each entry, [0] is the name, [1] contains further
//   attributes, and [2] contains the dependent entries
// * the variable "examples" contains the examples (a list of hashes)
//   the following properties must be set in each hash:
//   - _id (is used to communicate with the server
//   - text (is displayed for the user - this is the actual sentence
//        to be annotated)
//   - primary_rel / secondary_rel: relation values

old_chosen={};

var text_addr_map=undefined;

color_primary='#33ccff';
color_secondary='#88ee55';

function get_addr_text(addr) {
    var result='*UNKNOWN*';
    var next_list=schema;
    for (var i=0; i<addr.length; i++) {
	var entry=next_list[addr[i]];
	result=entry[0];
	next_list=entry[2];
    }
    return result;
}

function compute_text_addr_map(rels,addr) {
    for (var i=0; i<rels.length; i++) {
	var entry=rels[i];
	var addr_new=addr.concat([i]);
	text_addr_map[entry[0]]=addr_new;
	compute_text_addr_map(entry[2],addr_new);
    }
}
	

function get_text_addr(text) {
    if (!text_addr_map) {
	text_addr_map={};
	compute_text_addr_map(schema,[]);
    }
    var result=text_addr_map[text];
    if (!result) alert('not found:'+text);
    return result
}

function mark_primary(prefix0, addr) {
   var myref='cell:'+prefix0+':'+addr.join('.');
   var my_element=$(myref);
   if (!my_element) {
       alert("Element not found: "+myref);
       return;
   }
   my_element.style.background=color_primary;
   my_element.innerHTML=get_addr_text(addr)+'&nbsp;<img src="/static/asterisk_yellow.png">';
}

function mark_secondary(prefix0, addr) {
   var myref='cell:'+prefix0+':'+addr.join('.');
   var my_element=$(myref);
   if (!my_element) {
       alert("Element not found: "+myref);
       return;
   }
   my_element.style.background=color_secondary;
   my_element.innerHTML=get_addr_text(addr);
}

function mark_none(prefix0, addr) {
   var myref='cell:'+prefix0+':'+addr.join('.');
   var my_element=$(myref);
   if (!my_element) {
       alert("Element not found: "+myref);
       return;
   }
   my_element.style.background='#eeeeee';
   my_element.innerHTML=get_addr_text(addr);
}

function array_equals(a,b) {
    if (a.length!=b.length) {
	return false;
    } else {
	for (var i=0;i<a.length; i++) {
	    if (a[i]!=b[i]) {
		return false;
	    }
	}
	return true;
    }
}

function chosen(prefix0,addr) {
    a=old_chosen[prefix0];
    if (a && a.length) {
	var changed=false;
	for (var i=0; i<a.length; i++) {
	    if (a[i][0]==addr[0] &&
		!array_equals(addr,a[i])) {
		mark_none(prefix0,a[i]);
		a[i]=addr;
		changed=true;
	    }
	}
	if (!changed) {
	    for (var i=0; i<a.length; i++) {
		mark_none(prefix0,a[i]);
	    }
	    var addr2=a[0];
	    if (array_equals(addr,addr2)) {
		if (a.length>1) {
		    // unmark secondary
		    a=[a[0]];
		} else {
		    // none marked
		    a=[];
		}
	    } else if (a.length>1) {
		if (array_equals(addr,a[1])) {
		    // swap primary and secondary
		    a=[a[1],a[0]];
		} else {
		    a=[addr];
		}
	    } else {
		// mark as secondary
		a=[a[0],addr];
	    }
	}
    } else {
	// nothing marked => primary
	a=[addr];
    }
    data_prefix=prefix0.substring(4);
    if (a.length>=1) {
	mark_primary(prefix0,a[0]);
	dirty[data_prefix+':rel1']=get_addr_text(a[0]);
	if (a.length>=2) {
	    mark_secondary(prefix0,a[1]);
	    dirty[data_prefix+':rel2']=get_addr_text(a[1]);
	} else {
	    dirty[data_prefix+':rel2']='NULL';
	}
    } else {
	dirty[data_prefix+':rel1']='NULL';
    }
    resetTimeout();
    old_chosen[prefix0]=a;
}

function create_konn2_table(prefix0,prefix1,addr,indent,
			    schema_entry, example) {
    var prefix=prefix0+prefix1;
    var flags=schema_entry[1];
    if (example.word && flags['!'+example.word]) {
	return '';
    }
    result='<tr height="25px"><td id="cell:'+prefix+
	'" onclick="chosen(\''+prefix0+'\','+eval(JSON.stringify(addr))+')" style="padding-left:'+(indent*25+10)+'px;">'+schema_entry[0]+'</td></tr>';
    if (schema_entry[2]) {
	var children=schema_entry[2];
	for (var i=0; i<children.length; i++) {
	    if (get_addr_text(addr.concat([i]))!=schema_entry[2][i][0]) {
		alert(JSON.stringify([addr,schema_entry,get_addr_text(addr.concat([i]))]));
	    }
	    result+=create_konn2_table(prefix0,prefix1+'.'+i,
				       addr.concat([i]),indent+1,
				       children[i],example);
	}
    }
    return result;
}

function create_konn2(prefix,example) {
    result='<table class="konn2">';
    for (var i=0; i<schema.length; i++) {
	result+=create_konn2_table('tab:'+prefix,':'+i,[i],0,schema[i],example);
    }
    //TBD: add comment textarea
    result+='</table>';
    return result;
}

function create_widgets() {
    var s_widgets='';
    var primary_mark=[];
    var secondary_mark=[];
    for (var i=0; i<examples.length; i++) {
	var example=examples[i];
	s_widgets+='<div class="srctext" id="src:'+example._id+'">\n'+
	    example.text+"</div>";
	s_widgets+='<div align="right" style="margin-right:35px"><table><tr><td valign="top"><textarea cols="60" rows="5" id="'+example._id+':comment" onkeyup="after_blur(\''+example._id+':comment\')">';
	//TBD: escape comment
	if (example.comment) {
	    s_widgets+=example.comment.escapeHTML();
	}
	s_widgets+='</textarea></td><td>';
	s_widgets+=create_konn2(example._id,example);
	var a=[];
	if (example.rel1 && example.rel1!='NULL') {
	    var addr1=get_text_addr(example.rel1);
	    var prefix0='tab:'+example._id;
	    a.push(addr1);
	    primary_mark.push([prefix0,addr1]);
	    if (example.rel2 && example.rel2!='NULL') {
		var addr2=get_text_addr(example.rel2);
		a.push(addr2);
		secondary_mark.push([prefix0,addr2]);
	    }
	    //alert(JSON.stringify(a));
	    old_chosen[prefix0]=a;
	}
	s_widgets+='</td></tr></table></div>';
    }
    $("panel").innerHTML=s_widgets;
    for (var i=0; i<primary_mark.length; i++) {
	var entry=primary_mark[i];
	mark_primary(entry[0],entry[1]);
    }
    for (var i=0; i<secondary_mark.length; i++) {
	entry=secondary_mark[i];
	mark_secondary(entry[0],entry[1]);
    }
    $("status").innerHTML="loaded.";
}
