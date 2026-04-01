// DEFINE ALL TABS IN APPS
const all_tabs = ['home', 'mira', 'upload', 'about'];
const desktopBreakpoint = 600;
const defaultSidebarWidth = '25%';

// Define main page position
var mainPagePos = 0;

function getActiveTab() {
  for (let i = 0; i < all_tabs.length; i++) {
    var container = document.getElementById(all_tabs[i] + '-container');

    if (container && container.classList.contains('main-visible')) {
      return all_tabs[i];
    }
  }

  return null;
}

function updateMainPagePos(tabName) {
  var main = document.getElementById(tabName + '-main');

  if (main) {
    mainPagePos = findPosY(main);
  }
}

function setLayoutWidth(sidebar, main, width) {
  if (!sidebar || !main || !width) {
    return;
  }

  sidebar.dataset.sidebarWidth = width;
  sidebar.style.setProperty('--sidebar-width', width);
  sidebar.style.width = width;
  sidebar.style.flexBasis = width;
  main.style.width = 'calc(100% - ' + width + ')';
  main.style.flexBasis = 'calc(100% - ' + width + ')';
}

function clearLayoutWidth(sidebar, main) {
  if (!sidebar || !main) {
    return;
  }

  sidebar.style.removeProperty('--sidebar-width');
  sidebar.style.removeProperty('width');
  sidebar.style.removeProperty('flex-basis');
  main.style.removeProperty('width');
  main.style.removeProperty('flex-basis');
}

function getSidebarWidth(sidebar) {
  if (!sidebar) {
    return defaultSidebarWidth;
  }

  return sidebar.dataset.sidebarWidth || window.getComputedStyle(sidebar).getPropertyValue('--sidebar-width').trim() || defaultSidebarWidth;
}

function syncTabLayout(tabName) {
  var main = document.getElementById(tabName + '-main');
  var sidebar = document.getElementById(tabName + '-sidebar');

  if (!main || !sidebar) {
    return;
  }

  updateMainPagePos(tabName);

  if (window.innerWidth <= desktopBreakpoint) {
    clearLayoutWidth(sidebar, main);
    sidebar.style.position = 'relative';
    sidebar.style.top = '';
    sidebar.style.left = '';
    sidebar.style.height = 'auto';
    main.style.position = 'relative';
    main.style.right = '';
    return;
  }

  var width = getSidebarWidth(sidebar);
  setLayoutWidth(sidebar, main, width);

  if (window.pageYOffset > mainPagePos) {
    sidebar.style.position = 'fixed';
    sidebar.style.top = 0;
    sidebar.style.left = 0;
    sidebar.style.height = '100vh';

    main.style.position = 'absolute';
    main.style.right = 0;
  } else {
    sidebar.style.position = 'relative';
    sidebar.style.top = '';
    sidebar.style.left = '';
    sidebar.style.height = 'auto';
    main.style.position = 'relative';
    main.style.right = '';
  }
}

function initSidebarResizer(sidebarId, mainId, resizerId) {
  var sidebar = document.getElementById(sidebarId);
  var main = document.getElementById(mainId);
  var resizer = document.getElementById(resizerId);

  if (!sidebar || !main || !resizer || resizer.dataset.bound === 'true') {
    return;
  }

  resizer.dataset.bound = 'true';

  resizer.addEventListener('pointerdown', function(event) {
    if (window.innerWidth <= desktopBreakpoint) {
      return;
    }

    event.preventDefault();

    var startX = event.clientX;
    var startWidth = sidebar.getBoundingClientRect().width;
    var minWidth = 240;
    var maxWidth = 520;

    document.body.classList.add('is-resizing-sidebar');

    function onPointerMove(moveEvent) {
      var nextWidth = startWidth + (moveEvent.clientX - startX);
      var boundedWidth = Math.min(Math.max(nextWidth, minWidth), maxWidth);
      var width = boundedWidth + 'px';

      setLayoutWidth(sidebar, main, width);
      syncTabLayout('mira');
    }

    function onPointerUp() {
      document.body.classList.remove('is-resizing-sidebar');
      document.removeEventListener('pointermove', onPointerMove);
      document.removeEventListener('pointerup', onPointerUp);
    }

    document.addEventListener('pointermove', onPointerMove);
    document.addEventListener('pointerup', onPointerUp);
  });
}

// Function to find positon of an object
function findPosY(obj) {
  var curtop = 0;
  if (typeof (obj.offsetParent) != "undefined" && obj.offsetParent) {
    while (obj.offsetParent) {
      curtop += obj.offsetTop;
      obj = obj.offsetParent;
    }
    curtop += obj.offsetTop;
  }
  else if (obj.y)
    curtop += obj.y;
  return curtop;
}


window.onscroll = function(){
  for (let i = 0; i < all_tabs.length; i++) {
    
    var container_id = document.getElementById(all_tabs[i] + "-container");
    var check_class = container_id.classList.contains("main-visible");
    
    //alert(all_tabs[i]); alert(check_class);
    
    if (check_class === true) {
      syncTabLayout(all_tabs[i]);
      
    };
      
  };
  
};


window.onresize = function(){
  var activeTab = getActiveTab();

  if (activeTab) {
    syncTabLayout(activeTab);
  }
  
};

$(() => {
  initSidebarResizer('mira-sidebar', 'mira-main', 'mira-sidebar-resizer');
  var activeTab = getActiveTab();

  if (activeTab) {
    syncTabLayout(activeTab);
  }
  
  Shiny.addCustomMessageHandler("toggleActiveTab", (tab) => {
    //alert(tab.activeTab);
    var selected_tab = String(tab.activeTab);
    for (let i = 0; i < all_tabs.length; i++) {
      //alert(all_tabs[i]);
      var container_id = document.getElementById(all_tabs[i] + "-container");
      var tab_id = document.getElementById("tab_" + all_tabs[i]);
      if(all_tabs[i] === selected_tab){
        tab_id.classList.add("active");
        container_id.classList.add("main-visible");
        container_id.classList.remove("main-invisible");
        syncTabLayout(all_tabs[i]);
        //container_id.style.display = "block";
      }else{
        tab_id.classList.remove("active");
        container_id.classList.add("main-invisible");
        container_id.classList.remove("main-visible");
        //container_id.style.display = "none";
      };
    };
  });
  
  Shiny.addCustomMessageHandler("toggleAmpliconContent", (tag) => {
    //alert(tag.id); alert(tag.visible);
    var id = document.getElementById(tag.id);
    if(tag.visible === true){
      document.getElementById("seq_amplicon_library_label").textContent = tag.label;
      id.classList.add("main-visible");
      id.classList.remove("main-invisible");
    }else{
      id.classList.add("main-invisible");
      id.classList.remove("main-visible");
    };
  });  
  
  Shiny.addCustomMessageHandler("toggleContent", (tag) => {
    //alert(tag.id); alert(tag.visible);
    var id = document.getElementById(tag.id);
    if(tag.visible === true){
      id.classList.add("main-visible");
      id.classList.remove("main-invisible");
    }else{
      id.classList.add("main-invisible");
      id.classList.remove("main-visible");
    };
  });  
  
  Shiny.addCustomMessageHandler("toggleAssemblyContent", (tag) => {
    //alert(tag.id); alert(tag.visible);
    var id = document.getElementById(tag.id);
    if(tag.visible === true){
      id.classList.add("main-visible");
      id.classList.remove("main-invisible");
    }else{
      id.classList.add("main-invisible");
      id.classList.remove("main-visible");
    };
  }); 
  
  Shiny.addCustomMessageHandler("triggerBtn", (tag) => {
    //alert(tag.id); 
    var id = String(tag.id);
    document.getElementById(id).click();
  }); 
  
  Shiny.addCustomMessageHandler("triggerAssemblyBtn", (tag) => {
    //alert(tag.assembly_btn_id); alert(tag.samplesheet_tbl_id) 
    var assembly_btn_id = String(tag.assembly_btn_id);
    var samplesheet_tbl_id = String(tag.samplesheet_tbl_id)
    // FUNCTION TO GET REPORT CONTENTS
    var tbl = document.getElementById(samplesheet_tbl_id);
    Shiny.setInputValue('samplesheet_html', String(tbl.innerHTML), {priority: 'event'});
    // Activate the real assembly button
    document.getElementById(assembly_btn_id).click();
  }); 
  
  Shiny.addCustomMessageHandler("disableAssemblyBtn", (tag) => {
     //alert(tag.seq_run_id); alert(tag.assembly_btn_id); alert(tag.disabled);
     var seq_run_id = $("#"+tag.seq_run_id)[0].selectize;
     var assembly_btn_id = document.getElementById(tag.assembly_btn_id);
     var loading_icon_id = document.getElementById("assembly-loading-icon");
     var play_icon_id = document.getElementById("assembly-play-icon");
     if(tag.disabled === true){
       loading_icon_id.classList.remove("display-none");
       play_icon_id.classList.add("display-none");
       assembly_btn_id.classList.add("disabled");
       seq_run_id.disable();
     }else{
       play_icon_id.classList.remove("display-none");
       loading_icon_id.classList.add("display-none");
       assembly_btn_id.classList.remove("disabled");
       seq_run_id.enable();
     }
  }); 
  
  Shiny.addCustomMessageHandler("disableBtn", (tag) => {
     //alert(tag.id); alert(tag.disabled);
     var id = document.getElementById(tag.id);
     if(tag.disabled === true){
       id.classList.add("disabled");
     }else{
       id.classList.remove("disabled");
     }
  });  
  
  Shiny.addCustomMessageHandler("resizeITable", (tag) => {
     //alert(tag.height);
     var tbl_id = String(tag.tbl_id);
     var height = String(tag.height);
     var itables_anywidget = document.getElementById(tbl_id);
     itables_anywidget.style.height = height + "px";
  }); 

})























