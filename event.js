const express = require('express');
const router = express.Router();
const mysql = require('mysql2/promise');
const cookieParser = require('cookie-parser');
const { decrypt, encrypt } = require('../Script/change.js');

const pool = mysql.createPool({
    connectionLimit : 4 ,
    host : "localhost" ,
    user : "root" ,
    password : "xdrtyu" ,
    database : "campus_vibes"
});

router.use(express.urlencoded({ extended: true }));
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


router.get('/event', isAuthenticated , async (request,response) => {
    const userDataCookie = request.cookies.userData;
    const userData = JSON.parse(userDataCookie);
    const { Id } = request.query;
    const realId = decrypt(Id);
    const query = `select * from event where Club_ID = ?`;
    const clubNameQuery = `select Name from clubs where Club_ID = ?`;
    let clubLead = false;
    if(userData.clubId == Id){
        clubLead = true;
    }
    try {
        const [ events ] = await pool.query(query, [ realId ]);
        const [ clubName ] = await pool.query(clubNameQuery , [ realId ]);
        const details = {
            titleName : clubName[0].Name + ' Events' ,
            heading : clubName[0].Name + ' Events' ,
            user : userData.username ,
            userId : userData.userId ,
            result : events ,
            clubId : Id ,
            clubLead ,
            eventId : "" ,
            encrypt
        };
        response.render('event' , details);
    } catch (error) {
        response.render('Error', { message : error.message , layout : false });
    }
});

router.get('/edit' , isAuthenticated , async (request , response)=>{
    const userDataCookie = request.cookies.userData;
    const userData = JSON.parse(userDataCookie);
    const { eventId , clubId } = request.query;
    const realeventId = decrypt(eventId);
    const realclubId = decrypt(clubId);
    const query1 = `select * from event where Club_ID = ?`;
    const query2 = `select Date , Time , Location from event where Event_ID = ?`;
    const clubNameQuery = `select Name from clubs where Club_ID = ?`;
    let clubLead = false;
    try {
        const [ events ] = await pool.query(query1,[ realclubId ]);
        const [ specificEvent ] = await pool.query(query2 , [ realeventId ]);
        const [ clubName ] = await pool.query(clubNameQuery , [ realclubId ]);
        if(clubId == userData.clubId){
            clubLead = true;
        }
        const details = {
            titleName : clubName[0].Name + ' Events'  ,
            heading : clubName[0].Name + ' Events' ,
            result : events ,
            user : userData.username ,
            userId : userData.userId ,
            eventId : realeventId , 
            specificEvent , 
            clubId ,
            clubLead ,
            encrypt
        };
        response.render('event' , details);
    } catch (error) {
        response.render('Error', { message : error.message , layout : false });
    }
});

router.post('/edit' , isAuthenticated , async (request , response)=>{
    const userDataCookie = request.cookies.userData;
    const userData = JSON.parse(userDataCookie);
    const { eventId , date , time , location , clubId } = request.body;
    const realclubId = decrypt(clubId);
    const realeventId = decrypt(eventId);
    const query = `update event set Date = ? , Time = ? , Location = ? where Event_ID = ?`;
    const query2 = `select * from event where Club_ID = ?`;
    const clubNameQuery = `select Name from clubs where Club_ID = ?`;
    const values = [ date , time , location , realeventId ];
    let clubLead = false;
    try {
        await pool.query(query,values);
        const [ events ] = await pool.query(query2,[ realclubId ]);
        const [ clubName ] = await pool.query(clubNameQuery , [ realclubId ]);
        if(userData.clubId == clubId){
            clubLead = true;
        }
        const details = {
            titleName : clubName[0].Name + ' Events' , 
            heading : clubName[0].Name + ' Events' ,
            result : events ,  
            userId : userData.userId ,
            clubId  , 
            eventId : "" ,
            user : userData.username ,
            clubLead ,
            encrypt
        };
        response.render('event' , details );
    } catch (error) {
        response.render('Error', { message : error.message , layout : false });
    }
});

router.get('/allevents' , isAuthenticated , async (request , response)=>{
    const userDataCookie = request.cookies.userData;
    const userData = JSON.parse(userDataCookie);
    const query = `select * from event`;
    try{
        const [result] = await pool.query(query);
        const details = {
            titleName : "All Events" ,
            heading : "All Events" ,
            userId : userData.userId ,
            user : userData.username ,
            result : result ,
            encrypt
        }
        response.render('eventList' , details);
    }catch(error){
        response.render('Error', { message : error.message , layout : false });
    }
});

module.exports = router;
