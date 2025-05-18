function doPost(e) {
  var sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
  var data = JSON.parse(e.postData.contents);
  sheet.appendRow([
    new Date(),
    data.flame_status,
    data.blynk_data
  ]);
  return ContentService.createTextOutput("OK");
}
