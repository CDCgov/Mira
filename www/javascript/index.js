// DEFINE ALL TABS IN APPS
const all_tabs = ['home', 'mira', 'upload', 'about'];

// Define main page position
var startMainPagePos = -1; 

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
  
  var main = document.getElementsByClassName("page-main");

  if (startMainPagePos < 0) {
    main_pos = findPosY(main);
  }
  
  for (let i = 0; i < all_tabs.length; i++) {
    
    var container_id = document.getElementById(all_tabs[i] + "-container");
    var check_class = container_id.classList.contains("main-visible");
    
    //alert(all_tabs[i]); alert(check_class);
    
    if (check_class === true) {
      
      var main = document.getElementById(all_tabs[i] + "-main");
      var sidebar = document.getElementById(all_tabs[i] + "-sidebar");
      
      if (window.innerWidth > 600 && window.pageYOffset > main_pos) {
        
        //alert(window.innerWidth);
        //alert(window.pageYOffset);
        
        sidebar.style.position = "fixed";
        sidebar.style.top = 0;
        sidebar.style.left = 0;
        sidebar.style.height = "inherit";
    
        main.style.position = "absolute";
        main.style.right = 0;

      }else{
        
        sidebar.style.position = "relative";
        main.style.position = "relative";
    
      };
      
    };
      
  };
  
};


window.onresize = function(){

  var main_sidebar = document.getElementsByClassName("main-sidebar");
  var mira_main = document.getElementById("mira-main");
  var mira_sidebar = document.getElementById("mira-sidebar");
  
  if (window.innerWidth < 600) {
    
    //alert(window.innerWidth);
    main_sidebar.style.height = "100%";

    mira_sidebar.style.position = "relative";
    mira_sidebar.style.height = "auto";
    
    mira_main.style.position = "relative";
    mira_main.style.height = "auto";
    
  }  
  
};

$(() => {
  
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























