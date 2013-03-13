var Lemma = Backbone.Model.extend({
	defaults: function() { return {
	    lemma:'foo',
	    pos:'N',
	    senses:[]}; },
	idAttribute:'_id'
    });

var LemmaList = Backbone.Collection.extend({
	model:Lemma,
	url:"/pycwb/sensesJson",
	sortBy:'lemma'
    });

var Lemmas=new LemmaList();
var FilteredLemmas=new LemmaList();

var tokeninput_cls={
tokenList: "token-input-list-facebook",
token: "token-input-token-facebook",
tokenDelete: "token-input-delete-token-facebook",
selectedToken: "token-input-selected-token-facebook",
highlightedToken: "token-input-highlighted-token-facebook",
dropdown: "token-input-dropdown-facebook",
dropdownItem: "token-input-dropdown-item-facebook",
dropdownItem2: "token-input-dropdown-item2-facebook",
selectedDropdownItem: "token-input-selected-dropdown-item-facebook",
inputToken: "token-input-input-token-facebook"};


senseTemplate = _.template("<tr id=\"sense-tr-<%=lexunit_id%>\"><td><%= lexunit_id %></td><td class='descr' id=\"sense-descr-<%=lexunit_id%>\"><span placeholder=\"<%=lexunit_id%>\" descr=\"<%=description%>\"><%= description %></span></td><td class='edit_hover_class'><a class='icon-trash link-remove' orderid='<%= order_id %>'></a></td></tr>");
senseTemplateNew = _.template("<tr id=\"sense-tr-<%=lexunit_id%>\"><td><%= lexunit_id %></td><td class='descr' id=\"sense-descr-<%=lexunit_id%>\"><input orderid='<%= order_id %>' class='input-large sense-descr' value='<%= description %>'></td><td class='edit_hover_class'><a class='icon-trash link-remove' orderid='<%= order_id %>'></a></td></tr>");
var SenseListView = Backbone.View.extend({
	initialize: function() {
	    var that=this;
	    this.action_template=_.template($('#action-template').html());
	    this.render();
	},
	render: function() {
	    var that=this;
	    var senses=this.model.get('senses');
	    var need_save=this.model.get('need_save');
	    parts=[];
	    for (var i=0;i<senses.length;i++) {
		var x=senses[i];
		var ctx={'order_id':i,'lexunit_id':x[0],'description':x[1]};
		if (need_save) {
		    parts.push(senseTemplateNew(ctx));
		} else {
		    parts.push(senseTemplate(ctx));
		}
	    }
	    parts.push('<tr><td><input id="add_lu" class="input-small" placeholder="LexUnit"></td><td><input id="add_descr" class="input-medium" placeholder="Description"><button class="btn" id="add_btn">Add</button></td><td></td><tr>');
	    $('#sense-table').html(parts.join(''));
	    $('#sense-table .link-remove').bind('click', function(e) {
		    var order_id=parseInt($(this).attr('orderid'));
		    var senses=that.model.get('senses');
		    senses.splice(order_id,1);
		    if (need_save) {
			that.model.set('senses',senses);
			that.render();
		    } else {
			that.model.save({senses:senses},{success:function(){that.render()}});
		    }
		});
	    $('#add_btn').bind('click', function(e) {
		    var lu_id=parseInt($('#add_lu').val());
		    var text=$('#add_descr').val();
		    var senses=that.model.get('senses');
		    senses.push([lu_id,text]);
		    if (need_save) {
			that.model.set('senses',senses);
			that.render();
		    } else {
			that.model.save({senses:senses},{success:function(){that.render()}});
		    }
		});
	    if (need_save) {
		$('.sense-descr').keyup(function(ev) {
			var elm=$(ev.target);
			var id=parseInt(elm.attr('orderid'));
			var senses=that.model.get('senses');
			senses[id][1]=elm.val();
			that.model.set('senses',senses);
		    });
		$('#lemma-actions').html('Save to enable annotation actions');
	    } else {
		var that=this;
		$.ajax({url:'/pycwb/wsd_tasks/'+encodeURIComponent(that.model.id), dataType:'json',
			    success:function(data) {
			    that.render_action(data)
			}});
	    }
	    $('#sense-title').text('Senses for '+this.model.get('lemma'));
	    if (that.model.has('need_save')) {
		$('#sense-title').append(' <button class="btn btn-primary" id="save-btn">Save</button>');
		$('#save-btn').bind('click',function(){
			that.model.unset('need_save');
			that.model.save({},{success:function(){that.render()}});
		    });
	    } else {
		$('#sense-title').append(' <button class="btn btn-mini" id="edit-btn">edit</button>');
		$('#edit-btn').bind('click',function(){
			that.model.set('need_save',true);
			that.render();
		    });
	    }
	},
	render_action: function(data) {
	    var that=this;
	    $('#lemma-actions').html(this.action_template(data));
	    var inp=$('#input-action');
	    inp.tokenInput("/pycwb/get_users", {prePopulate:[{id:'wsduser',name:'wsduser'}],
			hintText: "Annotatoren?!", classes:tokeninput_cls});
	    $('#btn-add-remaining').bind('click', function(ev) { $.ajax({url:'/pycwb/wsd_tasks/'+encodeURIComponent(that.model.id),
				dataType:'json', type:'POST', contentType:'json',
				data:JSON.stringify({'method':'remaining','annotators':_.pluck(inp.tokenInput('get'),'name')}),
				success: function(result) {alert("created "+result.num_remaining+" tasks.");}})});
	    $('#btn-add-adjudicate').bind('click', function(ev) { $.ajax({url:'/pycwb/wsd_tasks/'+encodeURIComponent(that.model.id),
				dataType:'json', type:'POST', contentType:'json',
				data:JSON.stringify({'method':'wsdgold'}),
				success: function(result) {alert("create adjudication task: "+result.num_remaining+" spans");}})});
	}
    });

var lemmaTemplate = _.template("<td><%= lemma %></td><td><%= pos %></td><td> <%= senses.length %>");

var activeLemma=null;

var LemmaView = Backbone.View.extend({
	tagName:'tr',
	initialize: function() {
	    this.model.bind('change',this.render,this);
	},
	rerender: function() {
	    this.render();
	  //alert("foo");
	},
	render: function() {
	    this.$el.html(lemmaTemplate(this.model.toJSON()));
	    return this;
	},
	events: {
	    click: "openDetail",
	},
	openDetail: function() {
	    if (activeLemma) {
		activeLemma.$el.removeClass('active');
	    }
            this.$el.addClass('active');
	    activeLemma=this;
	    detailView=new SenseListView({model:this.model,el:$('sense-view')});
	}
    });


var LemmaListView = Backbone.View.extend({
	el:$('#lemmalist'),
	initialize: function() {
	    FilteredLemmas.bind('add', this.addOne, this);
	    FilteredLemmas.bind('reset',this.addAll, this);
	    Lemmas.fetch({success:function(){FilteredLemmas.reset(Lemmas.models)}});
	    var that=this;
	    var filter_input=$('#lemma_filter');
	    filter_input.keyup(function(ev) { that.updateFilter(filter_input.val()); });
	    $('#lemma_create_btn').bind('click', function(ev) { that.createLemma(filter_input.val()); });
	},
	updateFilter: function(prefix) {
	    var prefix_len=prefix.length;
	    models_new=Lemmas.filter(function(model) { return model.get('lemma').substring(0,prefix_len)==prefix; });
	    $('#lemmalist').empty();
	    FilteredLemmas.reset(models_new);
	},
	createLemma: function(lem) {
	    $.ajax({url:'/pycwb/sensesJson?create='+encodeURIComponent(lem),dataType:'json',success:function(data) {
			_.each(data,function(obj){obj.need_save=true;});
			Lemmas.add(data);FilteredLemmas.add(data);}});
	},
	addOne: function(lem) {
	    var view=new LemmaView({model:lem});
	    $('#lemmalist').append(view.render().el);
	},
	addAll: function() {
	    FilteredLemmas.each(this.addOne);
	}
    });
