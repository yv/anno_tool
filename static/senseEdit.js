var Lemma = Backbone.Model.extend({
	defaults: function() { return {
	    lemma:'foo',
	    pos:'N',
	    senses:[]}; },
    });

var LemmaList = Backbone.Collection.extend({
	model:Lemma,
	url:"/pycwb/sensesJson"
    });

var Lemmas=new LemmaList();

var SenseListView = Backbone.View.extend({
	initialize: function() {
	    this.render();
	},
	render: function() {
	    parts=[];
	    parts=_.map(this.model.get('senses'),function(x) { return '<tr><td>'+x[0]+'</td><td>'+x[1]+'</td></tr>'; });
	    $('#sense-table').html(parts.join(''));
	    $('#sense-title').text('Senses for '+this.model.get('lemma'));
	}});

var lemmaTemplate = _.template("<td><%= lemma %></td><td><%= pos %></td><td> <%= senses.length %>");

var LemmaView = Backbone.View.extend({
	tagName:'tr',
	render: function() {
	    this.$el.html(lemmaTemplate(this.model.toJSON()));
	    return this;
	},
	events: {
	    click: "openDetail"
	},
	openDetail: function() {
	    detailView=new SenseListView({model:this.model,el:$('sense-view')});
	}
    });

var LemmaListView = Backbone.View.extend({
	el:$('#lemmalist'),
	initialize: function() {
	    Lemmas.bind('add', this.addOne, this);
	    Lemmas.bind('reset',this.addAll, this);
	    Lemmas.fetch();
	    //alert("LemmaListView:initialize");
	},
	addOne: function(lem) {
	    var view=new LemmaView({model:lem});
	    //alert("LemmaListView:addOne");
	    this.$('#lemmalist').append(view.render().el);
	},
	addAll: function() {
	    Lemmas.each(this.addOne);
	}
    });

