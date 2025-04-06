const express = require('express');
const router = express.Router();
const mysql = require('mysql2/promise');
const cookieParser = require('cookie-parser');
const { encrypt } = require('../Script/change.js');

const pool = mysql.createPool({
    connectionLimit : 4 ,
    host : "localhost" ,
    user : "root" ,
    password : "xdrtyu" ,
    database : "campus_vibes"
});

router.use(express.urlencoded({ extended: true }));
router.use(cookieParser());


function loginStatus(userId){
    setTimeout( async ()=>{
        const updateQuery = `update users set Login_Status = ? where Roll_Number = ?`;
        const values = [ 0 , userId ];
        try {
            await pool.query(updateQuery , values);
        } catch (error) {
            console.log(error.message);
        }
    } , 60000);
};

router.get('/login', (request, response) => {
    response.render('logIn', { layout: false , message : "" , titleName : "Login" });
});


router.post('/dashboard' , async (request , response) => {
    const { userId, password } = request.body;
    const values = [userId];
    try {
        const [userCheck] = await pool.query(`select Name , Password , Login_Status from Users where Roll_Number = ?`, values);
        if ( userCheck.length ) {
            if (userCheck[0].Password === password && userCheck[0].Login_Status <= 3) {
                const clubIdCheck = `select Club_ID from Clubs where Club_Lead = (select Roll_Number from Users where Roll_Number = ?)`;
                const [clubId] = await pool.query(clubIdCheck , [ userId ]);
                let clubIdcheck = null;
                if(clubId.length){
                    clubIdcheck = encrypt(clubId[0].Club_ID);
                }
                const userData = {
                    userId : userId ,
                    username : userCheck[0].Name ,
                    clubId : clubIdcheck
                }
                const details = {
                    titleName : "Campus Vibes" , 
                    user : userCheck[0].Name ,
                    userId ,
                    heading : "" ,
                    encrypt
                };
                if(userCheck[0].Login_Status != 0){
                    const query = `update users set login_status = 0 where Roll_Number = ?`;
                    await pool.query(query , [ userId ]);
                }
                response.cookie('userData' , JSON.stringify(userData) , {
                    maxAge : 30 * 60 * 1000,
                    httpOnly : true ,
                    secure : false ,
                    sameSite : 'strict'
                }); 
                response.render('dashboard' , details );
            } else {
                if(userCheck[0].Login_Status < 3){
                    const query = `update users set login_status = login_status + 1 where Roll_Number = ?`;
                    await pool.query(query , [ userId ]);
                    response.render('logIn' , { titleName : "Login" , message : "Invalid Credentials . Please try again....." , layout : false});
                } else {
                    response.render('logIn' , { titleName : "Login" , message : "All attempts finished . Try again after 1 min" , layout : false});
                    loginStatus(userId);
                }
            }
        } else {
            response.render('logIn' , { titleName : "Login" , message : "Invalid Credentials . Please try again....." , layout : false});
        }
    } catch (err) {
        response.render('Error', { message : err.message , layout : false });
    }
});

router.get('/dashboard',async (req,res)=>{
    const userData = req.cookies.userData ? JSON.parse(req.cookies.userData) : null;
    const userId = userData ? userData.userId : null;
    if(userId){
        const details = {
            titleName : "Campus Vibes" , 
            user : userData.username ,
            userId ,
            heading : "" ,
            encrypt
        };
        res.render('dashboard' , details);
    }else{
        res.redirect('/login');
    }
});


router.get('/logout',(request,response)=>{
    response.clearCookie('userData');
    response.redirect('/login');
});

module.exports = router;
