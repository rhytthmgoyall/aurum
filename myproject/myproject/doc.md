auth
otp
pagination
cart
reviews
OOPs (class instead of function)

PAGINATION
search_view: selected_sort, categories, avg_rating, review_count, paginator, page_obj

LOGIN (Simple JWT)
a) login_page 
b) when we click login button
1. User logs in
   POST /api/token/

2. Backend returns:
   access token + refresh token

3. Frontend uses access token for protected APIs:
   Authorization: Bearer access_token

4. After some time, access token expires

5. Protected API returns 401 Unauthorized

6. Frontend calls:
   POST /api/token/refresh/

7. Backend checks the refresh token

8. If refresh token is valid:
   backend returns a new access token

9. Frontend retries the failed API request with the new access token

