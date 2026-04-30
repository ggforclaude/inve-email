/**
 * Improve_Eng/appsscript/Code.gs
 *
 * Google Apps Script 웹앱 — 테스트 결과를 수신하여 Sheets에 저장합니다.
 *
 * [배포 방법]
 * 1. script.google.com → 새 프로젝트
 * 2. 이 코드 붙여넣기
 * 3. 프로젝트 설정 → 스크립트 속성 추가:
 *    SHEET_ID = (Google Sheets ID)
 * 4. 배포 → 웹앱으로 배포
 *    - 다음 사용자로 실행: 나
 *    - 액세스 권한: 모든 사용자 (익명 포함)
 * 5. 배포 URL을 GitHub Secret APPS_SCRIPT_URL에 저장
 */

var PROPS   = PropertiesService.getScriptProperties();
var DOMAINS = ["listening", "grammar", "reading", "speaking"];

// GET 요청: HTML 페이지에서 답안 제출 (no-cors 방식)
function doGet(e) {
  try {
    var p = e.parameter;
    if (!p.date || !p.answers) {
      return _ok("missing params");
    }

    var date    = p.date;                        // "2026-04-30"
    var answers = p.answers.split(",");           // ["A","C","B",...]
    var correct = parseInt(p.correct || "0");

    // 영역별 acc 파싱: "2/3" 형식
    var accs = {};
    DOMAINS.forEach(function(d) {
      var val = (p[d] || "0/3").split("/").map(Number);
      accs[d] = val[1] > 0 ? (val[0] / val[1]).toFixed(3) : "0.000";
    });

    var ss = SpreadsheetApp.openById(PROPS.getProperty("SHEET_ID"));

    // Responses 시트에 저장
    var respSheet = _getOrCreate(ss, "Responses");
    respSheet.appendRow([
      date,
      p.answers,
      correct,
      accs.listening,
      accs.grammar,
      accs.reading,
      accs.speaking,
    ]);

    // Level_History 시트 업데이트 (중복이면 덮어쓰기)
    var histSheet = _getOrCreate(ss, "Level_History");
    var histData  = histSheet.getDataRange().getValues();
    var newRow    = [date, accs.listening, accs.grammar, accs.reading, accs.speaking];
    var rowIdx    = -1;
    for (var i = 0; i < histData.length; i++) {
      if (String(histData[i][0]) === date) { rowIdx = i + 1; break; }
    }
    if (rowIdx > 0) {
      histSheet.getRange(rowIdx, 1, 1, newRow.length).setValues([newRow]);
    } else {
      histSheet.appendRow(newRow);
    }

    return _ok("saved");

  } catch (err) {
    return _ok("error: " + err.message);
  }
}

function _getOrCreate(ss, name) {
  return ss.getSheetByName(name) || ss.insertSheet(name);
}

function _ok(msg) {
  return ContentService
    .createTextOutput(JSON.stringify({status: msg}))
    .setMimeType(ContentService.MimeType.JSON);
}
