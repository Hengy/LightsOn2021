
console.log("Connecting...");
var ledctrl_socket = new WebSocket('ws://192.168.0.41:31415/ledctrl');

var user_uuid = null;
var user_ip = null;

function getUserDetails(details) {
    user_uuid = details["uuid"];
    user_ip = detials["ip"];
}

ledctrl_socket.onopen = function(event) {
	console.log('Connected to: ' + event.currentTarget.URL);
};

ledctrl_socket.onerror = function(error) {
	console.log('WebSocket error: ' + error);
};

$("#idle-bttn").click(function() {
    msg = {"CMD":"IDLE", "uuid":user_uuid, "IP":user_ip}
    ledctrl_socket.send(JSON.stringify(msg));
});

$("#LED-bttn").click(function() {
    msg = {"CMD":"LED", "uuid":user_uuid, "IP":user_ip}
    ledctrl_socket.send(JSON.stringify(msg));
});

$("#dark-bttn").click(function() {
    msg = {"CMD":"DARK", "uuid":user_uuid, "IP":user_ip}
    ledctrl_socket.send(JSON.stringify(msg));
});

window.onload = getUserDetails({{data|tojson}});