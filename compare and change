//change.js

function encrypt(dbId){
    const apiId = ( 6 * dbId ) + 345;
    return apiId;
}


function decrypt(apiId){
    const dbId = ( apiId - 345 ) / 6;
    return dbId;
}

module.exports = { encrypt , decrypt };

//compare.js
const dayjs = require('dayjs');

const dateToCompare = dayjs('2025-03-23T21:00:00'); // Example datetime
const now = dayjs(); // Current datetime

console.log(dateToCompare.isBefore(now)); // true if dateToCompare is in the past
console.log(dateToCompare.isAfter(now));  // true if dateToCompare is in the future
console.log(dateToCompare.isSame(now));   // true if both are exactly the same
