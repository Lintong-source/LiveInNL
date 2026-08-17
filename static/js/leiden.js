
(function(){
  if(!window.L){
    document.querySelectorAll('.map-area').forEach(function(el){el.innerHTML='<div style="padding:24px;color:#777;font-size:13px">地图组件需要联网加载 OpenStreetMap / Leaflet。当前未加载成功，但正式部署时会正常显示。</div>';});
    return;
  }
  function dot(cls){return L.divIcon({className:'',html:'<div class="marker-dot '+cls+'"></div>',iconSize:[17,17],iconAnchor:[8,8],popupAnchor:[0,-8]});}

  var searchMap=L.map('searchAreaMap',{scrollWheelZoom:false});
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:18,attribution:'&copy; OpenStreetMap contributors'}).addTo(searchMap);
  var areas=[
    {n:'Leiden',c:[52.1601,4.4970],k:'core',t:'核心搜索区',d:'城市本体：大学、车站和主要学生生活设施集中。'},
    {n:'Oegstgeest',c:[52.1815,4.4690],k:'near',t:'近距离搜索',d:'紧邻 Leiden 西北侧，适合把 Bio Science Park / Leiden Centraal 通勤纳入考虑。'},
    {n:'Leiderdorp',c:[52.1590,4.5290],k:'near',t:'近距离搜索',d:'位于 Leiden 东侧，可结合自行车和公交通勤。'},
    {n:'Voorschoten',c:[52.1275,4.4480],k:'near',t:'骑车 / 火车',d:'Leiden 西南侧，有火车站，适合按实际学院位置计算通勤。'},
    {n:'Zoeterwoude',c:[52.1190,4.4930],k:'near',t:'近郊搜索',d:'Leiden 南侧，不同村落位置差异较大，建议看具体地址。'},
    {n:'Rijnsburg',c:[52.1895,4.4410],k:'near',t:'扩大搜索',d:'靠近 Oegstgeest / Katwijk，可结合公交和自行车。'},
    {n:'Katwijk',c:[52.2030,4.3985],k:'near',t:'扩大搜索',d:'西侧海边城镇，需结合公交 / 自行车计算通勤。'},
    {n:'Warmond',c:[52.1970,4.5020],k:'near',t:'扩大搜索',d:'Leiden 北侧小镇，适合看具体地址与公交 / 车站距离。'},
    {n:'Sassenheim',c:[52.2250,4.5220],k:'near',t:'火车通勤',d:'有火车站，可作为 Leiden 北侧通勤搜索范围。'},
    {n:'Voorhout',c:[52.2215,4.4840],k:'near',t:'火车通勤',d:'有火车站，可与 Sassenheim 一起搜索。'},
    {n:'Alphen aan den Rijn',c:[52.1290,4.6570],k:'commute',t:'更远通勤',d:'有铁路连接 Leiden，适合预算或房源紧张时扩大范围。'},
    {n:'Den Haag Centraal',c:[52.0809,4.3243],k:'commute',t:'通勤搜索',d:'如果接受火车通勤，海牙可作为重要的第二搜索圈。请按具体房源计算 door-to-door 时间。'},
    {n:'Leidschendam',c:[52.0917,4.3998],k:'commute',t:'通勤搜索',d:'可结合 Den Haag Mariahoeve / Voorburg 一带的铁路与公交通勤。'},
    {n:'Voorburg',c:[52.0705,4.3567],k:'commute',t:'通勤搜索',d:'位于 Leiden 与 Den Haag 通勤轴附近，建议按车站与房源具体位置判断。'},
    {n:'Den Haag Mariahoeve',c:[52.0909,4.3697],k:'commute',t:'铁路通勤',d:'靠近 Leidschendam / Voorburg，铁路方向适合纳入 Leiden 通勤搜索。'}
  ];
  var bounds=[];
  areas.forEach(function(a){
    var cls=a.k==='core'?'marker-leiden':(a.k==='commute'?'marker-commute':'marker-area');
    L.marker(a.c,{icon:dot(cls)}).addTo(searchMap).bindPopup('<div class="popup-title">'+a.n+'</div><div class="popup-meta">'+a.t+'</div><div style="font-size:12px;margin-top:5px">'+a.d+'</div>');
    bounds.push(a.c);
  });
  searchMap.fitBounds(bounds,{padding:[28,28]});

  var housingMap=L.map('housingMap',{scrollWheelZoom:false}).setView([52.161,4.485],13);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:18,attribution:'&copy; OpenStreetMap contributors'}).addTo(housingMap);
  var points=[
    {n:'SUWB · Boerhaave Housing',c:[52.1689,4.4656],cat:'housing',m:'Boerhaavelaan 72 一带；Leiden University / SCIS 科研人员住房路线中的代表性项目。'},
    {n:'DUWO · Leidse Schans',c:[52.1458,4.4960],cat:'housing',m:'大型学生住房片区，靠近 Leiden Lammenschans。'},
    {n:'DUWO · Langebrug',c:[52.1580,4.4905],cat:'housing',m:'市中心学生住房项目。'},
    {n:'DUWO · Kolffpad',c:[52.1688,4.4618],cat:'housing',m:'Bio Science Park 一带的学生住房项目。'},
    {n:'Xior · Verbeekstraat',c:[52.1725,4.4740],cat:'housing',m:'Verbeekstraat 11–29，Xior Leiden 学生住宿。'},
    {n:'Holland2Stay · MORE5',c:[52.1698,4.4560],cat:'housing',m:'Lise Meitnerhof / Bio Science Park，studio 和 apartment 项目。'},
    {n:'Leiden Centraal',c:[52.1662,4.4811],cat:'station',m:'莱顿主要火车站。'},
    {n:'Leiden Lammenschans',c:[52.1472,4.4927],cat:'station',m:'南侧火车站，紧邻 Leidse Schans 一带。'},
    {n:'Humanities · Lipsius',c:[52.1571,4.4820],cat:'university',m:'Cleveringaplaats 1，Faculty of Humanities 主要教学地点之一。'},
    {n:'Law · Kamerlingh Onnes',c:[52.1560,4.4920],cat:'university',m:'Steenschuur 25，法学院主要地点。'},
    {n:'Social & Behavioural Sciences',c:[52.1692,4.4685],cat:'university',m:'Wassenaarseweg 一带，社会与行为科学学院主要地点。'},
    {n:'Science · Gorlaeus',c:[52.1702,4.4590],cat:'university',m:'Einsteinweg 55，Science Campus 主要地点。'},
    {n:'Archaeology · Van Steenis',c:[52.1686,4.4610],cat:'university',m:'Einsteinweg 2，考古学主要地点之一。'},
    {n:'LUMC',c:[52.1667,4.4772],cat:'university',m:'医学 / LUMC，靠近 Leiden Centraal 西侧。'}
  ];
  var layerGroups={housing:L.layerGroup().addTo(housingMap),university:L.layerGroup().addTo(housingMap),station:L.layerGroup().addTo(housingMap)};
  points.forEach(function(p){var cls=p.cat==='housing'?'marker-house':p.cat==='university'?'marker-uni':'marker-station';L.marker(p.c,{icon:dot(cls)}).bindPopup('<div class="popup-title">'+p.n+'</div><div style="font-size:12px;margin-top:4px">'+p.m+'</div>').addTo(layerGroups[p.cat]);});
  document.querySelectorAll('.map-filter').forEach(function(btn){btn.addEventListener('click',function(){document.querySelectorAll('.map-filter').forEach(function(x){x.classList.remove('active')});btn.classList.add('active');var filter=btn.dataset.filter;Object.keys(layerGroups).forEach(function(k){if(filter==='all'||filter===k){housingMap.addLayer(layerGroups[k]);}else{housingMap.removeLayer(layerGroups[k]);}});});});
  setTimeout(function(){searchMap.invalidateSize();housingMap.invalidateSize();},300);
})();
