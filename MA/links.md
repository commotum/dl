| Course | Course ID | Progress URL | Status |
| --- | --- | --- | --- |
| 4th Grade Math | 75 | https://mathacademy.com/courses/75/progress | Linked in sidebar |
| 5th Grade Math | 30 | https://mathacademy.com/courses/30/progress | Linked in sidebar |
| Prealgebra | 99 | https://mathacademy.com/courses/99/progress | Linked in sidebar |
| Algebra I | 44 | https://mathacademy.com/courses/44/progress | Linked in sidebar |
| Geometry | 126 | https://mathacademy.com/courses/126/progress | Linked in sidebar |
| Algebra II |  |  | Selected in sidebar, no URL shown |
| Precalculus | 43 | https://mathacademy.com/courses/43/progress | Linked in sidebar |
| AP Calculus AB | 24 | https://mathacademy.com/courses/24/progress | Linked in sidebar |
| AP Calculus BC | 21 | https://mathacademy.com/courses/21/progress | Linked in sidebar |
| Mathematical Foundations I | 113 | https://mathacademy.com/courses/113/progress | Linked in sidebar |
| Mathematical Foundations II | 111 | https://mathacademy.com/courses/111/progress | Linked in sidebar |
| Mathematical Foundations III | 136 | https://mathacademy.com/courses/136/progress | Linked in sidebar |
| Unknown | 101 | https://mathacademy.com/courses/101/progress | Raw URL only |
| Unknown | 127 | https://mathacademy.com/courses/127/progress | Raw URL only |
| Unknown | 128 | https://mathacademy.com/courses/128/progress | Raw URL only |


1. Use my mathacademy cookies
2. Go to https://mathacademy.com/settings/course
3. Use the selector for #configureCourseButton (see html below) to open the options for courses
4. Use the selector for #configureCourseDialog-course (see html below) to select a course and grab the courses unique course-id number
5. Use the selector for #configureCourseDialog-buttonBar (see html below) to save the selected course
6. Go to https://mathacademy.com/courses/[COURSE-ID]/progress
7. Save the full html page like we did with the topics html pages
8. Go back to step 2 and loop through all courses

<div id="course">    
            Mathematical Foundations I

            <button id="configureCourseButton" class="button">Configure...</button>
        </div>

<div id="configureCourseDialog-course">    
        <label>Course</label>

        <select id="configureCourseDialog-courseSelect" autocomplete="off"><optgroup label="Elementary School"><option value="75">4th Grade Math</option><option value="30">5th Grade Math</option></optgroup><optgroup label="Middle School"><option value="31">6th Grade Math</option><option value="99">Prealgebra</option></optgroup><optgroup label="High School - Traditional"><option value="44">Algebra I</option><option value="126">Geometry</option><option value="51">Algebra II</option></optgroup><optgroup label="High School - Integrated Math"><option value="132">Integrated Math I</option><option value="133">Integrated Math II</option><option value="134">Integrated Math III</option><option value="43">Precalculus</option></optgroup><optgroup label="High School - Integrated Math (Honors)"><option value="127">Integrated Math I (Honors)</option><option value="128">Integrated Math II (Honors)</option><option value="101">Integrated Math III (Honors)</option></optgroup><optgroup label="Test Prep"><option value="120">SAT Math Fundamentals</option><option value="143">SAT Math Prep</option></optgroup><optgroup label="AP Courses"><option value="24">AP Calculus AB</option><option value="21">AP Calculus BC</option></optgroup><optgroup label="Mathematical Foundations"><option value="113">Mathematical Foundations I</option><option value="111">Mathematical Foundations II</option><option value="136">Mathematical Foundations III</option></optgroup><optgroup label="University"><option value="105">Calculus I</option><option value="106">Calculus II</option><option value="55">Linear Algebra</option><option value="54">Multivariable Calculus</option><option value="76">Methods of Proof</option><option value="61">Differential Equations</option><option value="109">Discrete Mathematics</option><option value="73">Probability &amp; Statistics</option><option value="145">Mathematics for Machine Learning</option><option value="154">Mathematical Methods for the Physical Sciences I</option><option value="155">Mathematical Methods for the Physical Sciences II</option></optgroup></select>
    </div>

<div id="configureCourseDialog-buttonBar">
        <button id="configureCourseDialog-saveButton" class="">Save</button>        
        <button id="configureCourseDialog-cancelButton">Cancel</button>
    </div>