/**
 * Improve_Eng/appsscript/Code.gs
 *
 * Google Apps Script 웹앱 — 테스트 결과를 수신하여 Sheets에 저장합니다.
 *
 * ── Responses 시트 컬럼 구조 (A~G) ──────────────────────────────────────
 *  A: 날짜         (예: 2026-05-06)
 *  B: 제출 답안    (예: A,B,C,A,B,D,A,...)  전체 답안 콤마 구분
 *  C: 총 정답 수   (예: 11)
 *  D: 듣기 정답률  (예: 0.667)  = 맞은수/전체
 *  E: 문법 정답률  (예: 1.000)
 *  F: 독해 정답률  (예: 0.333)
 *  G: 말하기 정답률 (예: 0.667)
 *
 * ── Level_History 시트 컬럼 구조 (A~E) ──────────────────────────────────
 *  A: 날짜
 *  B: 듣기 정확도
 *  C: 문법 정확도
 *  D: 독해 정확도
 *  E: 말하기 정확도
 *
 * [배포 방법]
 * 1. script.google.com → 새 프로젝트
 * 2. 이 코드 붙여넣기
 * 3. 프로젝트 설정 → 스크립트 속성 추가:
 *    SHEET_ID = (Google Sheets 파일 ID)
 * 4. 배포 → 웹앱으로 배포
 *    - 다음 사용자로 실행: 나
 *    - 액세스 권한: 모든 사용자 (익명 포함)
 * 5. 배포 URL을 GitHub Secret APPS_SCRIPT_URL에 저장
 */

var PROPS   = PropertiesService.getScriptProperties();
var DOMAINS = ["listening", "grammar", "reading", "speaking"];

var RESP_HEADERS = ["날짜", "제출답안(전체)", "총정답수", "듣기정답률", "문법정답률", "독해정답률", "말하기정답률"];
var HIST_HEADERS = ["날짜", "듣기정확도", "문법정확도", "독해정확도", "말하기정확도"];

// H열부터: 문항별 정오답 헤더 (듣기 6문항 + 문법3 + 독해3 + 말하기3 = 15문항)
var Q_HEADERS = [
  "듣기Short1", "듣기Short2",
  "듣기Med1",   "듣기Med2",
  "듣기Long1",  "듣기Long2",
  "문법1", "문법2", "문법3",
  "독해1", "독해2", "독해3",
  "말하기1", "말하기2", "말하기3"
];
var Q_START_COL = 8;  // H열 = 8번째 컬럼

// GET 요청: HTML 페이지에서 답안 제출 (no-cors 방식)
function doGet(e) {
  try {
    var p = e.parameter;
    if (!p.date || !p.answers) {
      return _ok("missing params: date=" + p.date + " answers=" + p.answers);
    }

    var date    = p.date;          // "2026-05-06"
    var answers = p.answers;       // "A,B,C,D,A,B,..." 콤마 구분 문자열
    var correct = parseInt(p.correct || "0");

    // 영역별 정답률 파싱: "2/6" 형식
    var accs = {};
    DOMAINS.forEach(function(d) {
      var raw = p[d] || "0/3";
      var val = raw.split("/").map(Number);
      accs[d] = (val[1] > 0) ? (val[0] / val[1]).toFixed(3) : "0.000";
    });

    var ss = SpreadsheetApp.openById(PROPS.getProperty("SHEET_ID"));

    // ── Responses 시트 저장 ──────────────────────────────────────────────
    var respSheet = _getOrCreate(ss, "Responses");
    _ensureHeaders(respSheet, RESP_HEADERS);
    _ensureQHeaders(respSheet);  // H열부터 문항별 헤더

    // 문항별 정오답 파싱: "O,X,O,O,X,..." → 배열
    var qResults = (p.results || "").split(",").filter(function(v) { return v !== ""; });

    // 기본 7개 + 문항별 O/X
    var newRespRow = [
      date, answers, correct,
      accs.listening, accs.grammar, accs.reading, accs.speaking
    ];
    for (var q = 0; q < qResults.length; q++) {
      newRespRow.push(qResults[q]);
    }

    // 같은 날짜가 이미 있으면 덮어쓰기, 없으면 추가
    var respData = respSheet.getDataRange().getValues();
    var respRow  = -1;
    for (var i = 1; i < respData.length; i++) {
      if (String(respData[i][0]) === date) { respRow = i + 1; break; }
    }
    if (respRow > 0) {
      respSheet.getRange(respRow, 1, 1, newRespRow.length).setValues([newRespRow]);
    } else {
      respSheet.appendRow(newRespRow);
    }

    // ── Level_History 시트 저장/업데이트 ────────────────────────────────
    var histSheet = _getOrCreate(ss, "Level_History");
    _ensureHeaders(histSheet, HIST_HEADERS);

    var histData = histSheet.getDataRange().getValues();
    var newHistRow = [date, accs.listening, accs.grammar, accs.reading, accs.speaking];
    var histRow = -1;
    for (var j = 1; j < histData.length; j++) {
      if (String(histData[j][0]) === date) { histRow = j + 1; break; }
    }
    if (histRow > 0) {
      histSheet.getRange(histRow, 1, 1, newHistRow.length).setValues([newHistRow]);
    } else {
      histSheet.appendRow(newHistRow);
    }

    return _ok("saved: " + date + " correct=" + correct);

  } catch (err) {
    return _ok("error: " + err.message);
  }
}

// ── 헬퍼 ────────────────────────────────────────────────────────────────────

function _getOrCreate(ss, name) {
  return ss.getSheetByName(name) || ss.insertSheet(name);
}

/**
 * A~G열 헤더가 비어있을 때만 설정합니다.
 */
function _ensureHeaders(sheet, headers) {
  var firstRow = sheet.getRange(1, 1, 1, headers.length).getValues()[0];
  var isEmpty  = firstRow.every(function(v) { return v === "" || v === null; });
  if (isEmpty) {
    sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
    sheet.getRange(1, 1, 1, headers.length).setFontWeight("bold");
    sheet.setFrozenRows(1);
  }
}

/**
 * H열부터 문항별 정오답 헤더를 설정합니다 (H1이 비어있을 때만).
 */
function _ensureQHeaders(sheet) {
  var h1 = sheet.getRange(1, Q_START_COL).getValue();
  if (h1 === "" || h1 === null) {
    var range = sheet.getRange(1, Q_START_COL, 1, Q_HEADERS.length);
    range.setValues([Q_HEADERS]);
    range.setFontWeight("bold");
    range.setBackground("#e8f0fe");  // 파란빛 배경으로 구분
  }
}

function _ok(msg) {
  return ContentService
    .createTextOutput(JSON.stringify({ status: msg }))
    .setMimeType(ContentService.MimeType.JSON);
}
