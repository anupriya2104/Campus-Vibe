const express = require('express');
const router = express.Router();
const cookieParser = require('cookie-parser');
const { encrypt } = require('../Script/change.js')


router.use(cookieParser());

const isAuthenticated = (request,response,next)=> {
    const userDataCookie = request.cookies.userData;
    try {
        const userData = userDataCookie && JSON.parse(userDataCookie);
        if(userData && userData.userId){
            request.userData = userData;
            return next();
        }else{
            response.render('login', { titleName : "Login" , message : "Not logged in" , layout : false });
        }
    } catch (error) {
        response.render('Error', { message : error.message , layout : false });
    }
}

router.get('/academic',(request,response)=>{
    const userDataCookie = request.cookies.userData;
    const userData = JSON.parse(userDataCookie);
    response.render('course' , { titleName : "Academic Events" , user : userData.username , userId : userData.userId , heading : "" , encrypt});
});

router.get('/non-academic', isAuthenticated , (request, response) => {
    const userDataCookie = request.cookies.userData;
    const userData = JSON.parse(userDataCookie);
    response.render('technical' , { titleName : "Non Academic Events" , user : userData.username , userId : userData.userId , heading : "" , encrypt});
});


router.get('/technical', isAuthenticated , async (request,response) => {
    const userDataCookie = request.cookies.userData;
    const userData = JSON.parse(userDataCookie);
    const details = {
        titleName : "Technical Events" , 
        user : userData.username , 
        userId : userData.userId ,
        encrypt ,
        heading : "Technical Events"
    }
    response.render('technicalEvents', details );
});

router.get('/non-technical', isAuthenticated , async (request,response) => {
    const userDataCookie = request.cookies.userData;
    const userData = JSON.parse(userDataCookie);
    const details = {
        titleName : "Non Technical Events" , 
        user : userData.username , 
        userId : userData.userId ,
        encrypt ,
        heading : "Non Technical Events"
    }
    response.render('nontechnicalEvents', details );
});

module.exports = router;
