SELECT photoID, photoPoster
               FROM Photo
               WHERE photoID in (
               SELECT photoID
               FROM Photo
               WHERE photoID IN 
               (SELECT photoID
                FROM SharedWith NATURAL JOIN BelongTo
                WHERE member_username = "%s") UNION
               (SELECT photoID
               FROM Photo Join Follow ON Photo.photoPoster = Follow.username_followed
               WHERE username_follower = "%s" AND followstatus = 1 AND allFollowers=1))