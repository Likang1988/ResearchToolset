/*
 Copyright (c) 2012-2017 Open Lab
 Permission is hereby granted, free of charge, to any person obtaining
 a copy of this software and associated documentation files (the
 "Software"), to deal in the Software without restriction, including
 without limitation the rights to use, copy, modify, merge, publish,
 distribute, sublicense, and/or sell copies of the Software, and to
 permit persons to whom the Software is furnished to do so, subject to
 the following conditions:

 The above copyright notice and this permission notice shall be
 included in all copies or substantial portions of the Software.

 THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
 EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
 MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
 NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
 LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
 OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
 WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
 */


function dateToRelative(localTime){
  var diff=new Date().getTime()-localTime;
  var ret="";

  var min=60000;
  var hour=3600000;
  var day=86400000;
  var wee=604800000;
  var mon=2629800000;
  var yea=31557600000;

  if (diff<-yea*2)
    ret ="## 年后".replace("##",(-diff/yea).toFixed(0));

  else if (diff<-mon*9)
    ret ="## 个月后".replace("##",(-diff/mon).toFixed(0));

  else if (diff<-wee*5)
    ret ="## 周后".replace("##",(-diff/wee).toFixed(0));

  else if (diff<-day*2)
    ret ="## 天后".replace("##",(-diff/day).toFixed(0));

  else if (diff<-hour)
    ret ="## 小时后".replace("##",(-diff/hour).toFixed(0));

  else if (diff<-min*35)
    ret ="大约一小时后";

  else if (diff<-min*25)
    ret ="大约半小时后";

  else if (diff<-min*10)
    ret ="几分钟后";

  else if (diff<-min*2)
    ret ="几分钟后"; // "in few minutes" 和 "in some minutes" 都翻译为几分钟后

  else if (diff<=min)
    ret ="刚刚";

  else if (diff<=min*5)
    ret ="几分钟前";

  else if (diff<=min*15)
    ret ="几分钟前"; // "few minutes ago" 和 "some minutes ago" 都翻译为几分钟前

  else if (diff<=min*35)
    ret ="大约半小时前";

  else if (diff<=min*75)
    ret ="大约一小时前";

  else if (diff<=hour*5)
    ret ="几小时前";

  else if (diff<=hour*24)
    ret ="## 小时前".replace("##",(diff/hour).toFixed(0));

  else if (diff<=day*7)
    ret ="## 天前".replace("##",(diff/day).toFixed(0));

  else if (diff<=wee*5)
    ret ="## 周前".replace("##",(diff/wee).toFixed(0));

  else if (diff<=mon*12)
    ret ="## 个月前".replace("##",(diff/mon).toFixed(0));

  else
    ret ="## 年前".replace("##",(diff/yea).toFixed(0));

  return ret;
}

//override date format i18n

Date.monthNames = ["一月","二月","三月","四月","五月","六月","七月","八月","九月","十月","十一月","十二月"];
// Month abbreviations. Change this for local month names
Date.monthAbbreviations = ["1月","2月","3月","4月","5月","6月","7月","8月","9月","10月","11月","12月"]; // 使用数字月份作为缩写
// Full day names. Change this for local month names
Date.dayNames =["星期日","星期一","星期二","星期三","星期四","星期五","星期六"];
// Day abbreviations. Change this for local month names
Date.dayAbbreviations = ["周日","周一","周二","周三","周四","周五","周六"];
// Used for parsing ambiguous dates like 1/2/2000 - default to preferring 'American' format meaning Jan 2.
// Set to false to prefer 'European' format meaning Feb 1
Date.preferAmericanFormat = false; // 设置为 false 以优先解析欧洲格式 (日/月/年)

Date.firstDayOfWeek = 1; // 设置每周的第一天为星期一
Date.defaultFormat = "yyyy-MM-dd"; // 设置默认日期格式
Date.masks = {
  fullDate:       "yyyy年MMMMd日 EEEE", // 例如：2025年四月17日 星期四
  shortTime:      "HH:mm" // 例如：16:05
};
Date.today="今天";

Number.decimalSeparator = ".";
Number.groupingSeparator = ",";
Number.minusSign = "-";
Number.currencyFormat = "###,##0.00"; // 货币格式保持不变，如果需要可修改



var millisInWorkingDay =28800000; // 保持不变，通常由服务器或配置决定
var workingDaysPerWeek =5; // 保持不变，通常由服务器或配置决定

function isHoliday(date) {
  // 保持默认的周六周日为假日，如果需要自定义节假日，需要修改 holidays 变量
  var friIsHoly =false;
  var satIsHoly =true;
  var sunIsHoly =true;

  var pad = function (val) {
    val = "0" + val;
    return val.substr(val.length - 2);
  };

  // 自定义节假日列表，格式 "#YYYY_MM_DD#" 或 "#MM_DD#"
  var holidays = "##"; // 例如: "#2025_10_01##2025_10_02##01_01#"

  var ymd = "#" + date.getFullYear() + "_" + pad(date.getMonth() + 1) + "_" + pad(date.getDate()) + "#";
  var md = "#" + pad(date.getMonth() + 1) + "_" + pad(date.getDate()) + "#";
  var day = date.getDay();

  return  (day == 5 && friIsHoly) || (day == 6 && satIsHoly) || (day == 0 && sunIsHoly) || holidays.indexOf(ymd) > -1 || holidays.indexOf(md) > -1;
}



var i18n = {
  YES:                 "是",
  NO:                  "否",
  FLD_CONFIRM_DELETE:  "确认删除吗？",
  INVALID_DATA:        "输入的数据格式无效。",
  ERROR_ON_FIELD:      "字段错误",
  OUT_OF_BOUDARIES:      "超出允许值范围：",
  CLOSE_ALL_CONTAINERS:"全部关闭？",
  DO_YOU_CONFIRM:      "您确定吗？",
  ERR_FIELD_MAX_SIZE_EXCEEDED:      "超出字段最大长度",
  WEEK_SHORT:      "周", // 周的缩写

  FILE_TYPE_NOT_ALLOWED:"不允许的文件类型。",
  FILE_UPLOAD_COMPLETED:"文件上传完成。",
  UPLOAD_MAX_SIZE_EXCEEDED:"超出最大文件大小",
  ERROR_UPLOADING:"上传出错",
  UPLOAD_ABORTED:"上传已中止",
  DROP_HERE:"将文件拖放到此处",

  FORM_IS_CHANGED:     "页面上有未保存的数据！",

  PIN_THIS_MENU: "固定此菜单",
  UNPIN_THIS_MENU: "取消固定此菜单",
  OPEN_THIS_MENU: "打开此菜单",
  CLOSE_THIS_MENU: "关闭此菜单",
  PROCEED: "继续？",

  PREV: "上一步",
  NEXT: "下一步",
  HINT_SKIP: "知道了，关闭此提示。",

  WANT_TO_SAVE_FILTER: "保存此筛选器",
  NEW_FILTER_NAME: "新筛选器名称",
  SAVE: "保存",
  DELETE: "删除",
  HINT_SKIP: "知道了，关闭此提示。", // 重复的键，保持翻译一致

  COMBO_NO_VALUES: "没有可用值...？",

  FILTER_UPDATED:"筛选器已更新。",
  FILTER_SAVED:"筛选器已成功保存。"

};


