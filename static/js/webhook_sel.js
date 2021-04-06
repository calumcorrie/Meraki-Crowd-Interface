var ds=document.getElementById("webhook_list");
var table=document.querySelector("#webhook_table > tbody");
var text_in=document.getElementById("webhook_input");


text_in.addEventListener("keydown", function(event) {
	if (event.key == "Enter") {
		event.stopImmediatePropagation();
		event.preventDefault();
		add_address(event);
	}
}, true); 

function add_address(event){
	var new_row = document.createElement("tr");
	var new_cell = document.createElement("td");
	
	var new_othercell = document.createElement("td");
	var new_butt = document.getElementById("trashcanhidden").cloneNode(true);
	
	var new_option = document.createElement("option");
	
	var address = text_in.value;
	text_in.value="";
	
	new_cell.innerHTML = address;
	
	new_option.innerHTML = address;
	new_option.selected = true;	
	new_option.id = "op_" + option_index;
	
	new_butt.id="";
	new_butt.addEventListener("click",remove,false);
	
	new_othercell.appendChild(new_butt);
	
	new_row.id = "row_" + option_index;
	new_row.appendChild(new_cell);
	new_row.appendChild(new_othercell);
	
	table.insertBefore(new_row, table.lastElementChild);	
	ds.appendChild(new_option);
	option_index++;
}

function remove(event){
	var row = event.target.parentElement.parentElement;
	var rownum = parseInt(row.id.slice(- row.id.length + row.id.lastIndexOf("_") +  1));
	ds.removeChild(ds.querySelector("#op_"+rownum));
	table.removeChild(row);
}

var buttons = table.querySelectorAll("img.trashcan");
for (var i = 0; i < buttons.length; i++){
	buttons[i].addEventListener("click", remove, false);
}

document.getElementById("add_button").addEventListener("click", add_address, false);